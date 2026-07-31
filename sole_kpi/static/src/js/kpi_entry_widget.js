/** @odoo-module **/
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const CIRC = 2 * Math.PI * 34; // r=34 → circumference ≈ 213.6

const STATUS_CONFIG = {
    green: { label: "On Track",        color: "#28a745", bg: "#d4edda", text: "#155724" },
    amber: { label: "Needs Attention", color: "#b08800", bg: "#fff3cd", text: "#856404" },
    red:   { label: "At Risk",         color: "#dc3545", bg: "#f8d7da", text: "#721c24" },
    black: { label: "Critical",        color: "#212529", bg: "#d3d3d3", text: "#212529" },
    grey:  { label: "No Data",         color: "#9e9e9e", bg: "#e9ecef", text: "#495057" },
};

function fmtNum(val, unit) {
    if (unit === "currency") {
        if (val >= 1_000_000) return (val / 1_000_000).toFixed(1) + "M";
        if (val >= 1_000) return (val / 1_000).toFixed(0) + "K";
        return String(val | 0);
    }
    if (unit === "percentage") return val.toFixed(1);
    return val % 1 === 0 ? String(val | 0) : val.toFixed(1);
}

const UNIT_LABEL = { currency: "KES", percentage: "%", count: "", hours: "hrs" };

export class KpiAchievementWidget extends Component {
    static template = "sole_kpi.KpiAchievementWidget";
    static props = { ...standardFieldProps };

    get pct()    { return this.props.record.data.achievement_pct || 0; }
    get status() { return this.props.record.data.status || "grey"; }
    get cfg()    { return STATUS_CONFIG[this.status] || STATUS_CONFIG.grey; }

    get dashArray() {
        const capped = Math.min(Math.max(this.pct, 0), 100);
        return `${(capped / 100) * CIRC} ${CIRC}`;
    }

    get displayPct() { return Math.round(this.pct) + "%"; }

    get indicatorName() {
        const v = this.props.record.data.indicator_id;
        if (!v) return "—";
        // Odoo 19: Many2one is a Record object with .display_name
        return v.display_name || (Array.isArray(v) ? v[1] : String(v));
    }

    get periodName() {
        const v = this.props.record.data.period_id;
        if (!v) return "—";
        return v.display_name || (Array.isArray(v) ? v[1] : String(v));
    }

    get unit() { return this.props.record.data.unit || "count"; }

    get actualDisplay() {
        return fmtNum(this.props.record.data.actual || 0, this.unit);
    }

    get targetDisplay() {
        return fmtNum(this.props.record.data.target || 0, this.unit);
    }

    get unitLabel() { return UNIT_LABEL[this.unit] || ""; }
}

registry.category("fields").add("kpi_achievement", {
    component: KpiAchievementWidget,
    supportedTypes: ["float"],
});
