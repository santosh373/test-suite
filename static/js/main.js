// Auto-refresh running runs
document.addEventListener('DOMContentLoaded', () => {
  // JSON format helpers for textareas
  document.querySelectorAll('.mono-input').forEach(el => {
    el.addEventListener('blur', () => {
      try {
        const v = el.value.trim();
        if (v && (v.startsWith('{') || v.startsWith('['))) {
          el.value = JSON.stringify(JSON.parse(v), null, 2);
        }
      } catch (_) {}
    });
  });
});
