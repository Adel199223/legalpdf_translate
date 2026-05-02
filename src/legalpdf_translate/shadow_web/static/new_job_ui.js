export function syncNewJobTaskControlsInto({
  panels = [],
  switches = [],
  activeTask = "translation",
} = {}) {
  const selectedTask = activeTask === "interpretation" ? "interpretation" : "translation";
  for (const panel of panels || []) {
    panel.classList.toggle("hidden", panel.dataset.taskPanel !== selectedTask);
  }
  for (const button of switches || []) {
    const selected = button.dataset.task === selectedTask;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-selected", selected ? "true" : "false");
  }
}
