// Kararsızım — küçük JS iyileştirmeleri.
// Tüm formlar JavaScript kapalıyken de çalışır; JS yalnızca deneyimi iyileştirir.

// Anket oluşturma: JS yokken 5 alan görünür (boşlar yok sayılır). JS ile en az 2 alan görünür,
// "Seçenek ekle" ile 5'e kadar çıkılır, "✕" ile alanlar silinir (en az 2 kalır).
(function () {
  var list = document.querySelector("[data-option-list]");
  if (!list) return;

  var MIN = 2;
  var rows = Array.prototype.slice.call(list.querySelectorAll("[data-option-row]"));
  var addButton = list.querySelector("[data-add-option]");

  function input(row) { return row.querySelector("input"); }
  function visibleRows() { return rows.filter(function (row) { return !row.hidden; }); }

  function refresh() {
    var visible = visibleRows();
    visible.forEach(function (row, position) {
      row.querySelector("[data-option-label]").textContent = "Seçenek " + (position + 1);
      input(row).required = position < MIN;
      var remove = row.querySelector("[data-remove-option]");
      remove.hidden = visible.length <= MIN;
      remove.setAttribute("aria-label", "Seçenek " + (position + 1) + " alanını sil");
    });
    addButton.hidden = visible.length >= rows.length;
  }

  // Başlangıç: dolu son alana (ve en az MIN alana) kadar göster, gerisini gizle.
  var lastFilled = -1;
  rows.forEach(function (row, index) { if (input(row).value.trim()) lastFilled = index; });
  var shown = Math.max(MIN, lastFilled + 1);
  rows.forEach(function (row, index) { row.hidden = index >= shown; });

  addButton.addEventListener("click", function () {
    var next = rows.find(function (row) { return row.hidden; });
    if (!next) return;
    next.hidden = false;
    refresh();
    input(next).focus();
  });

  list.addEventListener("click", function (event) {
    var button = event.target.closest("[data-remove-option]");
    if (!button) return;
    var row = button.closest("[data-option-row]");
    if (visibleRows().length <= MIN) return;
    input(row).value = "";
    row.hidden = true;
    list.insertBefore(row, addButton); // gizlenen alan listenin sonuna taşınır; görünen sıra korunur
    rows.splice(rows.indexOf(row), 1);
    rows.push(row);
    refresh();
    var firstVisible = visibleRows()[0];
    if (firstVisible) input(firstVisible).focus();
  });

  refresh();
})();

// Çift gönderim engeli: POST formları gönderilirken butonlar pasifleşir; ikinci gönderim yok sayılır.
// Tarayıcı sayfayı geri/ileri önbelleğinden açarsa (pageshow) butonlar yeniden etkinleşir.
(function () {
  var BUSY_LABEL = "Gönderiliyor…";

  function release(form) {
    form.removeAttribute("data-submitting");
    Array.prototype.forEach.call(form.querySelectorAll("button[type=submit]"), function (button) {
      button.disabled = false;
      button.removeAttribute("aria-busy");
      if (button.dataset.label) button.textContent = button.dataset.label;
    });
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form.matches || !form.matches("form[method=post]")) return;

    if (form.hasAttribute("data-submitting")) {
      event.preventDefault();
      return;
    }
    form.setAttribute("data-submitting", "");

    // Pasifleştirme, gönderim başladıktan sonra yapılır; böylece form verisi etkilenmez.
    window.setTimeout(function () {
      Array.prototype.forEach.call(form.querySelectorAll("button[type=submit]"), function (button) {
        button.dataset.label = button.textContent;
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        if (button.classList.contains("btn--block")) button.textContent = BUSY_LABEL;
      });
    }, 0);
  });

  window.addEventListener("pageshow", function (event) {
    if (!event.persisted) return;
    Array.prototype.forEach.call(document.querySelectorAll("form[data-submitting]"), release);
  });
})();
