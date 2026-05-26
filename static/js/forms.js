document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const required = form.querySelectorAll("[required]");
      const invalid = Array.from(required).find((el) => !el.value);
      if (invalid) {
        event.preventDefault();
        showToast("Please complete required fields", "error");
      }
    });
  });
});
