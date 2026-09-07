document.querySelectorAll("[data-intake-review-form]").forEach((form) => {
    const choices = Array.from(form.querySelectorAll("[data-intake-select]"));
    const count = form.querySelector("[data-selected-count]");
    const submit = form.querySelector("[data-create-selected]");
    const selectReady = form.querySelector("[data-select-ready]");

    const updateSelection = () => {
        const selected = choices.filter((choice) => choice.checked).length;
        count.textContent = `${selected} selected`;
        submit.textContent = `Create selected candidates (${selected})`;
        submit.disabled = selected === 0;
    };

    choices.forEach((choice) => choice.addEventListener("change", updateSelection));
    selectReady?.addEventListener("click", () => {
        choices
            .filter((choice) => choice.dataset.ready === "true")
            .forEach((choice) => {
                choice.checked = true;
            });
        updateSelection();
    });
    updateSelection();
});
