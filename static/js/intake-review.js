document.querySelectorAll("[data-intake-review-form]").forEach((form) => {
    const choices = Array.from(form.querySelectorAll("[data-intake-select]"));
    const count = form.querySelector("[data-selected-count]");
    const submit = form.querySelector("[data-create-selected]");
    const selectReady = form.querySelector("[data-select-ready]");
    const readyChoices = choices.filter(
        (choice) => choice.dataset.ready === "true",
    );

    const updateSelection = () => {
        const selected = choices.filter((choice) => choice.checked).length;
        count.textContent = `${selected} selected`;
        const actionLabel = submit.dataset.actionLabel || "Create selected candidates";
        submit.textContent = `${actionLabel} (${selected})`;
        submit.disabled = selected === 0;
        if (selectReady) {
            const allReadySelected =
                readyChoices.length > 0 &&
                readyChoices.every((choice) => choice.checked);
            selectReady.textContent = allReadySelected
                ? "Clear selection"
                : "Select all ready";
            selectReady.setAttribute("aria-pressed", String(allReadySelected));
            selectReady.disabled = readyChoices.length === 0;
        }
    };

    choices.forEach((choice) => choice.addEventListener("change", updateSelection));
    selectReady?.addEventListener("click", () => {
        const allReadySelected =
            readyChoices.length > 0 &&
            readyChoices.every((choice) => choice.checked);
        if (allReadySelected) {
            choices.forEach((choice) => {
                choice.checked = false;
            });
        } else {
            readyChoices.forEach((choice) => {
                choice.checked = true;
            });
        }
        updateSelection();
    });
    updateSelection();
});
