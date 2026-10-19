/** @odoo-module **/

// totals computed in the browser; the server already sends "1,234.56" for the rest
export function formatAmount(value) {
    const n = typeof value === "string" ? parseFloat(value.replace(/,/g, "")) : value;
    return (Number.isFinite(n) ? n : 0).toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}
