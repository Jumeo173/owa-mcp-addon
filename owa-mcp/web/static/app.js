// Общие утилиты

// Часы в навбаре
function updateClock() {
    const el = document.getElementById('clock');
    if (!el) return;
    const now = new Date();
    el.textContent = now.toLocaleString('ru-RU');
}
setInterval(updateClock, 1000);
updateClock();

// Обёртка над fetch с обработкой ошибок
async function api(path, opts) {
    const r = await fetch(path, opts);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
}
