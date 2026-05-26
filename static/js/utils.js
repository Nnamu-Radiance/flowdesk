window.showToast = (message, type = "info") => {
  const container = document.getElementById("notifications-container");
  if (!container) return;
  const el = document.createElement("div");
  const color = type === "error" ? "bg-red-500" : type === "success" ? "bg-green-600" : "bg-blue-600";
  el.className = `${color} text-white px-4 py-2 rounded shadow mb-2`;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => el.remove(), 3500);
};
