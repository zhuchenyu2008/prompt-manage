import io
import json
import os
import shutil
import tempfile
import unittest
import zipfile

from PIL import Image
from werkzeug.datastructures import FileStorage


TEST_ROOT = tempfile.mkdtemp(prefix="prompt-manager-tests-")
os.environ["DB_PATH"] = os.path.join(TEST_ROOT, "data.sqlite3")
os.environ["COVER_DIR"] = os.path.join(TEST_ROOT, "covers")
os.environ["SECRET_KEY"] = "test-secret"
os.environ["FLASK_DEBUG"] = "1"

import app as prompt_app  # noqa: E402


def png_bytes(size=(24, 16)):
    output = io.BytesIO()
    Image.new("RGB", size, (70, 120, 180)).save(output, "PNG")
    return output.getvalue()


class AppCoverTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_ROOT, ignore_errors=True)

    def setUp(self):
        if os.path.exists(prompt_app.DB_PATH):
            conn = prompt_app.get_db()
            conn.execute("DELETE FROM versions")
            conn.execute("DELETE FROM prompts")
            conn.execute("UPDATE settings SET value='off' WHERE key='auth_mode'")
            conn.execute("UPDATE settings SET value='' WHERE key='auth_password_hash'")
            conn.execute("UPDATE settings SET value='0' WHERE key='auth_session_version'")
            conn.commit()
            conn.close()
        shutil.rmtree(prompt_app.COVER_DIR, ignore_errors=True)
        if not os.path.exists(prompt_app.DB_PATH):
            prompt_app.init_db()
        else:
            prompt_app.ensure_cover_dir(prompt_app.COVER_DIR)
        prompt_app.app.config.update(TESTING=True)
        self.client = prompt_app.app.test_client()

    def csrf(self):
        self.client.get("/prompt/new")
        with self.client.session_transaction() as session:
            return session["_csrf_token"]

    def create_prompt_with_cover(self, filename="cover.bin", content_type="text/plain"):
        response = self.client.post(
            "/prompt/new",
            data={
                "_csrf_token": self.csrf(),
                "name": "带封面的提示词",
                "content": "两行预览内容",
                "cover_alt": "测试封面",
                "cover_focus_x": "25",
                "cover_focus_y": "75",
                "image_file": (io.BytesIO(png_bytes()), filename, content_type),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 302)
        conn = prompt_app.get_db()
        row = conn.execute("SELECT * FROM prompts").fetchone()
        conn.close()
        return row

    def test_real_image_content_is_used_instead_of_client_mime(self):
        row = self.create_prompt_with_cover()
        self.assertIsNone(row["image_data"])
        self.assertEqual(row["cover_mime"], "image/png")
        self.assertEqual((row["cover_focus_x"], row["cover_focus_y"]), (25, 75))
        self.assertTrue(os.path.isfile(os.path.join(prompt_app.COVER_DIR, row["cover_file"])))
        self.assertTrue(os.path.isfile(os.path.join(prompt_app.COVER_DIR, row["cover_thumb"])))

    def test_invalid_upload_preserves_other_form_fields(self):
        response = self.client.post(
            "/prompt/new",
            data={
                "_csrf_token": self.csrf(),
                "name": "不能丢失的名称",
                "content": "不能丢失的正文",
                "image_file": (io.BytesIO(b"broken"), "broken.png", "image/png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("不能丢失的名称", response.get_data(as_text=True))
        self.assertIn("不能丢失的正文", response.get_data(as_text=True))
        conn = prompt_app.get_db()
        count = conn.execute("SELECT COUNT(*) AS count FROM prompts").fetchone()["count"]
        conn.close()
        self.assertEqual(count, 0)

    def test_index_does_not_embed_base64_and_cover_route_works(self):
        row = self.create_prompt_with_cover()
        index_response = self.client.get("/")
        self.assertEqual(index_response.status_code, 200)
        self.assertNotIn(b"data:image", index_response.data)
        self.assertIn(f"/prompt/{row['id']}/cover/thumb".encode(), index_response.data)
        response = self.client.get(f"/prompt/{row['id']}/cover/thumb")
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_index_uses_one_shared_lightbox_for_multiple_covers(self):
        self.create_prompt_with_cover()
        self.create_prompt_with_cover()
        html = self.client.get("/").get_data(as_text=True)
        self.assertEqual(html.count('id="coverLightbox"'), 1)
        self.assertEqual(html.count('class="card-image-wrap media-image-wrap overlay-image-wrap cover-lightbox-trigger"'), 2)

    def test_cover_filter_and_zip_settings_are_rendered(self):
        self.create_prompt_with_cover()
        self.assertNotIn("带封面的提示词", self.client.get("/?cover=without").get_data(as_text=True))
        settings = self.client.get("/settings")
        self.assertEqual(settings.status_code, 200)
        self.assertIn("导出 ZIP（推荐）", settings.get_data(as_text=True))

    def test_locked_cover_is_not_directly_accessible(self):
        row = self.create_prompt_with_cover()
        conn = prompt_app.get_db()
        conn.execute("UPDATE prompts SET require_password=1 WHERE id=?", (row["id"],))
        prompt_app.set_setting(conn, "auth_mode", "per")
        conn.commit()
        conn.close()
        self.assertEqual(self.client.get(f"/prompt/{row['id']}/cover/full").status_code, 404)
        with self.client.session_transaction() as session:
            session["auth_session_version"] = "0"
            session["unlocked_prompts"] = [row["id"]]
        response = self.client.get(f"/prompt/{row['id']}/cover/full")
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_removing_cover_deletes_both_files_after_commit(self):
        row = self.create_prompt_with_cover()
        full_path = os.path.join(prompt_app.COVER_DIR, row["cover_file"])
        thumb_path = os.path.join(prompt_app.COVER_DIR, row["cover_thumb"])
        response = self.client.post(
            f"/prompt/{row['id']}",
            data={
                "_csrf_token": self.csrf(),
                "name": row["name"],
                "content": "两行预览内容",
                "remove_image": "1",
                "cover_focus_x": "50",
                "cover_focus_y": "50",
            },
        )
        self.assertEqual(response.status_code, 302)
        conn = prompt_app.get_db()
        updated = conn.execute("SELECT * FROM prompts WHERE id=?", (row["id"],)).fetchone()
        conn.close()
        self.assertIsNone(updated["cover_file"])
        self.assertFalse(os.path.exists(full_path))
        self.assertFalse(os.path.exists(thumb_path))

    def test_version_rollback_does_not_change_cover(self):
        row = self.create_prompt_with_cover()
        original_cover = row["cover_file"]
        original_version = row["current_version_id"]
        response = self.client.post(
            f"/prompt/{row['id']}",
            data={
                "_csrf_token": self.csrf(),
                "name": row["name"],
                "content": "第二个版本",
                "do_save_version": "1",
                "bump_kind": "patch",
                "cover_focus_x": "50",
                "cover_focus_y": "50",
            },
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            f"/prompt/{row['id']}/rollback/{original_version}",
            data={"_csrf_token": self.csrf(), "bump_kind": "patch"},
        )
        self.assertEqual(response.status_code, 302)
        conn = prompt_app.get_db()
        updated = conn.execute("SELECT cover_file FROM prompts WHERE id=?", (row["id"],)).fetchone()
        conn.close()
        self.assertEqual(updated["cover_file"], original_cover)

    def test_legacy_base64_migration_is_idempotent(self):
        data_url = prompt_app.encode_data_url(png_bytes(), "image/png")
        conn = prompt_app.get_db()
        conn.execute(
            "INSERT INTO prompts(name, tags, image_data) VALUES(?,?,?)",
            ("旧封面", "[]", data_url),
        )
        conn.commit()
        prompt_app.migrate_legacy_covers(conn)
        prompt_app.migrate_legacy_covers(conn)
        row = conn.execute("SELECT * FROM prompts").fetchone()
        conn.close()
        self.assertIsNone(row["image_data"])
        self.assertTrue(row["cover_file"])
        self.assertEqual(len(os.listdir(prompt_app.COVER_DIR)), 2)

    def test_zip_export_and_import_round_trip(self):
        original = self.create_prompt_with_cover()
        conn = prompt_app.get_db()
        archive = prompt_app.build_zip_export(conn)
        conn.close()
        with zipfile.ZipFile(archive) as bundle:
            manifest = json.loads(bundle.read("manifest.json"))
            self.assertEqual(manifest["schema_version"], 2)
            self.assertTrue(manifest["prompts"][0]["cover"]["file"].startswith("images/"))

        archive.seek(0)
        upload = FileStorage(stream=archive, filename="backup.zip")
        payload = prompt_app.load_import_payload(upload)
        conn = prompt_app.get_db()
        prompt_app.apply_import_payload(conn, payload)
        restored = conn.execute("SELECT * FROM prompts").fetchone()
        conn.close()
        self.assertEqual(restored["name"], original["name"])
        self.assertEqual(restored["cover_alt"], "测试封面")
        self.assertTrue(os.path.isfile(os.path.join(prompt_app.COVER_DIR, restored["cover_file"])))

    def test_invalid_import_does_not_replace_existing_data(self):
        self.create_prompt_with_cover()
        invalid = {
            "prompts": [{
                "name": "坏备份",
                "image_data": "data:image/png;base64,not-valid-base64",
            }]
        }
        conn = prompt_app.get_db()
        with self.assertRaises(prompt_app.CoverImageError):
            prompt_app.apply_import_payload(conn, invalid)
        count = conn.execute("SELECT COUNT(*) AS count FROM prompts").fetchone()["count"]
        conn.close()
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
