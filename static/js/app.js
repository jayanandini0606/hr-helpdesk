// AI-Powered HR Helpdesk Interactive UI Handlers

document.addEventListener("DOMContentLoaded", function () {
  // Auto-dismiss alerts after 5 seconds
  const alerts = document.querySelectorAll(".alert");
  alerts.forEach(function (alert) {
    setTimeout(function () {
      alert.style.transition = "opacity 0.5s ease";
      alert.style.opacity = "0";
      setTimeout(function () {
        alert.remove();
      }, 500);
    }, 5000);
  });

  // Table row click navigation if data-href is present
  const clickableRows = document.querySelectorAll("tr[data-href]");
  clickableRows.forEach(function (row) {
    row.style.cursor = "pointer";
    row.addEventListener("click", function () {
      window.location.href = row.getAttribute("data-href");
    });
  });
});
