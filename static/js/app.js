document.querySelectorAll('[data-add]').forEach(function(b) {
  b.addEventListener('click', async function() {
    try {
      var r = await fetch('/cart/add/' + b.dataset.add, { method: 'POST' });
      var d = await r.json();
      if (d.ok) {
        document.querySelectorAll('.cart-count').forEach(function(x) {
          x.textContent = d.count;
        });
        var old = b.textContent;
        b.textContent = '✓';
        setTimeout(function() { b.textContent = old || '+'; }, 900);
      }
    } catch (e) {}
  });
});

document.querySelectorAll('[data-wish]').forEach(function(b) {
  b.addEventListener('click', async function() {
    try {
      var r = await fetch('/wishlist/' + b.dataset.wish, { method: 'POST' });
      if (r.status === 401) {
        location = '/login?next=' + encodeURIComponent(location.pathname);
        return;
      }
      var d = await r.json();
      if (d.ok) b.classList.toggle('liked', d.added);
    } catch (e) {}
  });
});

setTimeout(function() {
  document.querySelectorAll('.toast').forEach(function(x) { x.remove(); });
}, 3500);
