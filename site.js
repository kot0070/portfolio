(function () {
  var links = Array.prototype.slice.call(document.querySelectorAll(".site-nav a"));
  var sections = links
    .map(function (link) {
      var href = link.getAttribute("href") || "";
      if (href.charAt(0) !== "#") return null;
      return document.getElementById(href.slice(1));
    })
    .filter(Boolean);

  if ("IntersectionObserver" in window) {
    var active = null;
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          active = entry.target.id;
        });
        links.forEach(function (link) {
          var on = link.getAttribute("href") === "#" + active;
          if (on) link.setAttribute("aria-current", "true");
          else link.removeAttribute("aria-current");
        });
      },
      { rootMargin: "-45% 0px -50% 0px", threshold: 0 }
    );
    sections.forEach(function (section) {
      observer.observe(section);
    });
  }

  var button = document.getElementById("expand-faq");
  if (!button) return;
  button.addEventListener("click", function () {
    var items = Array.prototype.slice.call(document.querySelectorAll("#faq details"));
    var openAll = items.some(function (item) {
      return !item.open;
    });
    items.forEach(function (item) {
      item.open = openAll;
    });
    button.textContent = openAll ? "Collapse all answers" : "Expand all answers";
    button.setAttribute("aria-pressed", openAll ? "true" : "false");
  });
})();
