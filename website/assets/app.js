const copyButtons = document.querySelectorAll(".copy-trigger");

copyButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    const sourceId = button.getAttribute("data-copy-source");
    if (!sourceId) {
      return;
    }

    const source = document.getElementById(sourceId);
    if (!source) {
      return;
    }

    const text = source.innerText.trim();
    const originalLabel = button.innerText;

    try {
      await navigator.clipboard.writeText(text);
      button.innerText = "Copied";
      window.setTimeout(() => {
        button.innerText = originalLabel;
      }, 1400);
    } catch (error) {
      button.innerText = "Copy failed";
      window.setTimeout(() => {
        button.innerText = originalLabel;
      }, 1400);
    }
  });
});
