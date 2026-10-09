// Frontend for the expenses API. The API URL comes from config.js,
// which the deploy workflow generates from the CloudFormation outputs.
const API_URL = (window.APP_CONFIG && window.APP_CONFIG.apiUrl || "").replace(/\/$/, "");

const CATEGORY_LABELS = {
  alimentacao: "Alimentação",
  transporte: "Transporte",
  moradia: "Moradia",
  lazer: "Lazer",
  saude: "Saúde",
  educacao: "Educação",
  outros: "Outros",
};

const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

const form = document.getElementById("expense-form");
const message = document.getElementById("message");
const tableBody = document.getElementById("expenses");
const summaryList = document.getElementById("summary");
const totalLabel = document.getElementById("total");

async function api(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (response.status === 204) return null;
  const body = await response.json();
  if (!response.ok) throw new Error(body.message || `HTTP ${response.status}`);
  return body;
}

function showMessage(text, isError = false) {
  message.textContent = text;
  message.className = isError ? "error" : "ok";
}

function renderExpenses(expenses) {
  tableBody.replaceChildren();
  for (const expense of expenses) {
    const row = document.createElement("tr");
    const [year, month, day] = expense.date.split("-");
    const cells = [
      `${day}/${month}/${year}`,
      expense.description,
      CATEGORY_LABELS[expense.category] || expense.category,
      money.format(expense.amount),
    ];
    cells.forEach((value, index) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      if (index === 3) cell.className = "num";
      row.appendChild(cell);
    });

    const actions = document.createElement("td");
    const remove = document.createElement("button");
    remove.textContent = "Excluir";
    remove.className = "link";
    remove.addEventListener("click", () => deleteExpense(expense.id));
    actions.appendChild(remove);
    row.appendChild(actions);

    tableBody.appendChild(row);
  }
}

function renderSummary(summary) {
  totalLabel.textContent = money.format(summary.total);
  summaryList.replaceChildren();
  for (const [category, value] of Object.entries(summary.by_category)) {
    const item = document.createElement("li");
    item.textContent = `${CATEGORY_LABELS[category] || category}: ${money.format(value)}`;
    summaryList.appendChild(item);
  }
}

async function refresh() {
  try {
    const [expenses, summary] = await Promise.all([api("/expenses"), api("/expenses/summary")]);
    renderExpenses(expenses);
    renderSummary(summary);
  } catch (error) {
    showMessage(`Não foi possível carregar os dados: ${error.message}`, true);
  }
}

async function deleteExpense(id) {
  try {
    await api(`/expenses/${encodeURIComponent(id)}`, { method: "DELETE" });
    showMessage("Despesa excluída.");
    await refresh();
  } catch (error) {
    showMessage(error.message, true);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(form));
  if (!data.date) delete data.date;
  data.amount = Number(data.amount);

  try {
    await api("/expenses", { method: "POST", body: JSON.stringify(data) });
    form.reset();
    showMessage("Despesa adicionada.");
    await refresh();
  } catch (error) {
    showMessage(error.message, true);
  }
});

if (!API_URL) {
  showMessage("Configure apiUrl em config.js.", true);
} else {
  refresh();
}
