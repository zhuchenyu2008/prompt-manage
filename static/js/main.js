// Enhanced UI interactions and animations
// Theme manager: follow system by default, allow manual override
(function(){
  const KEY = 'theme'; // 'light' | 'dark' | null (auto)
  const mql = window.matchMedia('(prefers-color-scheme: dark)');

  function getManual() {
    try { return localStorage.getItem(KEY); } catch (_) { return null; }
  }
  function setManual(val) {
    try {
      if (val === 'light' || val === 'dark') localStorage.setItem(KEY, val);
      else localStorage.removeItem(KEY);
    } catch (_) {}
  }
  function effectiveTheme() {
    const manual = getManual();
    if (manual === 'light' || manual === 'dark') return manual;
    return mql.matches ? 'dark' : 'light';
  }
  function applyTheme(manual) {
    const mode = (manual === 'light' || manual === 'dark') ? manual : null;
    if (mode) document.documentElement.setAttribute('data-theme', mode);
    else document.documentElement.removeAttribute('data-theme');
    syncThemeColor(mode ? mode : effectiveTheme(), !!mode);
  }
  function syncThemeColor(mode, isManual) {
    // If manual override, inject a dynamic meta to override media-based ones
    let meta = document.querySelector('meta[name="theme-color"]#dynamic-theme');
    if (isManual) {
      if (!meta) {
        meta = document.createElement('meta');
        meta.name = 'theme-color';
        meta.id = 'dynamic-theme';
        document.head.appendChild(meta);
      }
      meta.setAttribute('content', mode === 'dark' ? '#0b0b0f' : '#ffffff');
    } else {
      if (meta) meta.remove();
    }
  }

  // Init on load (honors inline head script state)
  applyTheme(getManual());
  // Follow system when in auto
  mql.addEventListener('change', () => {
    if (!getManual()) applyTheme(null);
  });

  // Expose global setter for optional UI
  window.setTheme = function(t) {
    if (t === 'light' || t === 'dark') { setManual(t); applyTheme(t); }
    else { setManual(null); applyTheme(null); }
  };
})();

document.addEventListener('DOMContentLoaded', () => {
  const APP_LANG = (window.APP_LANG || 'zh');
  // Theme toggle with smooth transition (two states: light/dark)
  const btn = document.getElementById('themeToggle');
  if (btn) {
    btn.addEventListener('click', () => {
      const saved = (function(){ try { return localStorage.getItem('theme'); } catch(_) { return null; } })();
      let next;
      if (saved === 'light') next = 'dark';
      else if (saved === 'dark') next = 'light';
      else {
        // In auto mode: toggle from current effective theme
        const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        next = prefersDark ? 'light' : 'dark';
      }
      window.setTheme(next);
    });
  }

  // Enhanced tag suggestions with autocomplete
  const tagsInput = document.getElementById('tagsInput');
  if (tagsInput) {
    let suggestions = [];
    let currentSuggestion = '';
    
    // Fetch suggestions
    fetch('/api/tags')
      .then(r => r.json())
      .then(list => {
        suggestions = list;
        createAutocompleteDropdown();
      })
      .catch(() => {});

    // Create dropdown for suggestions
    function createAutocompleteDropdown() {
      const dropdown = document.createElement('div');
      dropdown.className = 'tag-suggestions';
      dropdown.style.cssText = `
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 8px;
        max-height: 200px;
        overflow-y: auto;
        z-index: 100;
        display: none;
        box-shadow: 0 4px 16px var(--shadow);
      `;
      tagsInput.parentNode.style.position = 'relative';
      tagsInput.parentNode.appendChild(dropdown);

      // Show/hide dropdown
      tagsInput.addEventListener('focus', showSuggestions);
      tagsInput.addEventListener('input', showSuggestions);
      tagsInput.addEventListener('blur', () => {
        setTimeout(() => dropdown.style.display = 'none', 200);
      });
    }

    function showSuggestions() {
      const dropdown = tagsInput.parentNode.querySelector('.tag-suggestions');
      if (!dropdown) return;

      const val = tagsInput.value;
      const parts = val.replace(/，/g, ',').split(',');
      const lastPart = parts[parts.length - 1] || '';
      const lastTag = lastPart.trim();

      if (lastTag.length >= 1) {
        const matches = suggestions.filter(tag => 
          tag.toLowerCase().includes(lastTag.toLowerCase())
        ).slice(0, 5);

        if (matches.length > 0) {
          dropdown.innerHTML = matches.map(tag => 
            `<div class="tag-suggestion" style="padding: 8px 12px; cursor: pointer; transition: background 0.2s ease;" data-tag="${tag}">
              ${highlightMatch(tag, lastTag)}
            </div>`
          ).join('');
          
          dropdown.style.display = 'block';
          
          // Add click handlers
          dropdown.querySelectorAll('.tag-suggestion').forEach(item => {
            item.addEventListener('click', () => {
              const tag = item.dataset.tag;
              parts[parts.length - 1] = tag;
              tagsInput.value = parts.join(', ') + ', ';
              tagsInput.focus();
              dropdown.style.display = 'none';
            });
            
            item.addEventListener('mouseenter', () => {
              item.style.background = 'var(--card)';
            });
            
            item.addEventListener('mouseleave', () => {
              item.style.background = '';
            });
          });
        } else {
          dropdown.style.display = 'none';
        }
      } else {
        dropdown.style.display = 'none';
      }
    }

    function highlightMatch(tag, search) {
      if (!search) return tag;
      const regex = new RegExp(`(${search})`, 'gi');
      return tag.replace(regex, '<strong style="color: var(--primary);">$1</strong>');
    }

    // Enhanced comma/Enter handling
    tagsInput.addEventListener('keydown', (e) => {
      if (e.key === ',' || e.key === 'Enter') {
        e.preventDefault();
        const val = tagsInput.value;
        const parts = val.replace(/，/g, ',').split(',');
        const last = (parts[parts.length - 1] || '').trim();
        
        if (last.length >= 2) {
          const match = suggestions.find(t => 
            t.toLowerCase().startsWith(last.toLowerCase())
          );
          if (match) {
            parts[parts.length - 1] = match;
            tagsInput.value = parts.join(', ') + ', ';
          } else {
            tagsInput.value = parts.join(', ') + ', ';
          }
        } else {
          tagsInput.value = parts.join(', ') + ', ';
        }
      }
    });
  }

  // Enhanced flash notifications with auto-dismiss
  const flashWrap = document.querySelector('.flash-wrap');
  if (flashWrap) {
    const flashes = flashWrap.querySelectorAll('.flash');
    flashes.forEach((flash, index) => {
      // Auto-dismiss after 5 seconds
      setTimeout(() => {
        flash.style.animation = 'slideInRight 0.4s ease-out reverse';
        setTimeout(() => flash.remove(), 400);
      }, 5000 + (index * 500));
      
      // Add close button
      const closeBtn = document.createElement('button');
      closeBtn.innerHTML = '×';
      closeBtn.style.cssText = `
        position: absolute;
        top: 8px;
        right: 8px;
        background: none;
        border: none;
        font-size: 18px;
        cursor: pointer;
        color: var(--muted);
        transition: color 0.2s ease;
      `;
      closeBtn.addEventListener('click', () => {
        flash.style.animation = 'slideInRight 0.4s ease-out reverse';
        setTimeout(() => flash.remove(), 400);
      });
      closeBtn.addEventListener('mouseenter', () => {
        closeBtn.style.color = 'var(--fg)';
      });
      flash.appendChild(closeBtn);
    });
  }

  // Smooth scroll for anchor links
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      e.preventDefault();
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        target.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });
      }
    });
  });

  // Enhanced form interactions
  const forms = document.querySelectorAll('form');
  forms.forEach(form => {
    form.addEventListener('submit', () => {
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.disabled = true;
        const processing = APP_LANG === 'en' ? 'Processing...' : '处理中...';
        submitBtn.innerHTML = '<span class="loading"></span> ' + processing;
        
        // Re-enable after 5 seconds (fallback)
        setTimeout(() => {
          submitBtn.disabled = false;
          const fallback = APP_LANG === 'en' ? 'Submit' : '提交';
          submitBtn.innerHTML = submitBtn.dataset.originalText || fallback;
        }, 5000);
      }
    });
  });

  // Store original button text
  document.querySelectorAll('button[type="submit"]').forEach(btn => {
    btn.dataset.originalText = btn.textContent;
  });

  // Enhanced card hover effects
  const cards = document.querySelectorAll('.card');
  cards.forEach(card => {
    card.addEventListener('mouseenter', () => {
      card.style.transform = 'translateY(-4px) scale(1.01)';
    });
    
    card.addEventListener('mouseleave', () => {
      card.style.transform = '';
    });
  });

  // Color picker + preview sync
  const colorInput = document.getElementById('color');
  const colorPicker = document.getElementById('colorPicker');
  const colorSwatch = document.getElementById('colorSwatch');
  const colorClearBtn = document.getElementById('colorClearBtn');
  if (colorInput && colorPicker && colorSwatch) {
    const isValidHex = (s) => /^#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$/.test((s || '').trim());
    const expandHex = (s) => {
      s = (s || '').trim();
      if (!s) return '';
      if (!isValidHex(s)) return '';
      if (s.length === 4) {
        return '#' + s.slice(1).split('').map(c => c + c).join('').toLowerCase();
      }
      return s.toLowerCase();
    };
    const applySwatch = (val) => {
      const v = expandHex(val);
      colorSwatch.style.background = v ? v : 'transparent';
    };

    // Init swatch from current text value only (empty -> transparent)
    applySwatch(colorInput.value);

    colorPicker.addEventListener('input', () => {
      const v = (colorPicker.value || '').toLowerCase();
      colorInput.value = v;
      colorInput.classList.remove('color-invalid');
      applySwatch(v);
    });

    colorInput.addEventListener('input', () => {
      const raw = colorInput.value;
      if (!raw) {
        colorInput.classList.remove('color-invalid');
        applySwatch('');
        return;
      }
      if (isValidHex(raw)) {
        colorInput.classList.remove('color-invalid');
        // Sync picker with expanded hex (#RGB -> #RRGGBB)
        const v = expandHex(raw);
        try { colorPicker.value = v; } catch (_) {}
        applySwatch(v);
      } else {
        colorInput.classList.add('color-invalid');
      }
    });

    colorInput.addEventListener('blur', () => {
      // Normalize on blur
      const v = expandHex(colorInput.value);
      if (v) colorInput.value = v;
    });

    // Swatch opens native color picker
    const openPicker = () => {
      try { colorPicker.showPicker ? colorPicker.showPicker() : colorPicker.click(); } catch (_) { colorPicker.click(); }
    };
    colorSwatch.addEventListener('click', openPicker);
    colorSwatch.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPicker(); }
    });

    // Clear button
    if (colorClearBtn) {
      colorClearBtn.addEventListener('click', () => {
        colorInput.value = '';
        colorInput.classList.remove('color-invalid');
        applySwatch('');
      });
    }
  }

  // Ripple effect for buttons
  document.querySelectorAll('.btn').forEach(button => {
    button.addEventListener('click', function(e) {
      const ripple = document.createElement('span');
      const rect = this.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height);
      const x = e.clientX - rect.left - size / 2;
      const y = e.clientY - rect.top - size / 2;
      
      ripple.style.cssText = `
        position: absolute;
        width: ${size}px;
        height: ${size}px;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.3);
        top: ${y}px;
        left: ${x}px;
        pointer-events: none;
        animation: ripple 0.6s ease-out;
      `;
      
      this.appendChild(ripple);
      setTimeout(() => ripple.remove(), 600);
    });
  });

  // Add ripple animation
  const style = document.createElement('style');
  style.textContent = `
    @keyframes ripple {
      to {
        transform: scale(4);
        opacity: 0;
      }
    }
  `;
  document.head.appendChild(style);

  // Intersection Observer for scroll animations
  const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
      }
    });
  }, observerOptions);

  // Observe elements for animation
  document.querySelectorAll('.card, .version-item, .fold').forEach(el => {
    el.style.opacity = '1';
    el.style.transform = 'translateY(0)';
  });
});

// Add utility functions
const utils = {
  // Debounce function for search
  debounce: (func, wait) => {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  },

  // Format date for display
  formatDate: (dateString) => {
    const date = new Date(dateString);
    const locale = (window.APP_LANG === 'en') ? 'en-US' : 'zh-CN';
    return date.toLocaleDateString(locale, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  },

  // Copy to clipboard with notification
  copyToClipboard: async (text, button = null) => {
    try {
      await navigator.clipboard.writeText(text);
      
      if (button) {
        const originalText = button.textContent;
        button.textContent = (window.APP_LANG === 'en') ? 'Copied!' : '已复制!';
        button.style.background = 'var(--ins)';
        button.style.color = 'var(--text-on-success)';
        
        setTimeout(() => {
          button.textContent = originalText;
          button.style.background = '';
          button.style.color = '';
        }, 2000);
      }
    } catch (err) {
      console.error('Failed to copy: ', err);
    }
  }
};

// Export utils for global use
window.utils = utils;
