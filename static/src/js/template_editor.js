/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, useRef, onWillStart } from "@odoo/owl";

export class TemplateEditor extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.imgRef = useRef("img");
        this.docId = this.props.action.params.document_id;
        this.state = useState({
            png: null,
            fields: [],
            zones: [],
            partnerName: "",
            currentField: null,
            drawing: null,
        });
        onWillStart(async () => {
            const data = await this.orm.call(
                "invoice.ocr.document", "get_template_editor_data", [this.docId]
            );
            this.state.png = data.page_png;
            this.state.fields = data.fields;
            this.state.zones = data.zones || [];
            this.state.partnerName = data.partner_name;
            this.state.currentField = data.fields.length ? data.fields[0][0] : null;
        });
    }

    _rel(ev) {
        const rect = this.imgRef.el.getBoundingClientRect();
        return {
            x: Math.min(1, Math.max(0, (ev.clientX - rect.left) / rect.width)),
            y: Math.min(1, Math.max(0, (ev.clientY - rect.top) / rect.height)),
        };
    }

    onMouseDown(ev) {
        const p = this._rel(ev);
        this.state.drawing = { x0: p.x, y0: p.y, x1: p.x, y1: p.y };
    }
    onMouseMove(ev) {
        if (!this.state.drawing) {
            return;
        }
        const p = this._rel(ev);
        this.state.drawing.x1 = p.x;
        this.state.drawing.y1 = p.y;
    }
    onMouseUp() {
        const d = this.state.drawing;
        this.state.drawing = null;
        if (!d || !this.state.currentField) {
            return;
        }
        const x0 = Math.min(d.x0, d.x1);
        const x1 = Math.max(d.x0, d.x1);
        const y0 = Math.min(d.y0, d.y1);
        const y1 = Math.max(d.y0, d.y1);
        if (x1 - x0 > 0.005 && y1 - y0 > 0.005) {
            this.state.zones.push({ field_key: this.state.currentField, x0, y0, x1, y1 });
        }
    }

    removeZone(index) {
        this.state.zones.splice(index, 1);
    }
    fieldLabel(key) {
        const found = this.state.fields.find((f) => f[0] === key);
        return found ? found[1] : key;
    }
    zoneStyle(z) {
        return (
            `left:${z.x0 * 100}%; top:${z.y0 * 100}%;` +
            ` width:${(z.x1 - z.x0) * 100}%; height:${(z.y1 - z.y0) * 100}%;` +
            ` border:2px solid #3B82F6; background:rgba(59,130,246,0.15);` +
            ` pointer-events:none;`
        );
    }
    get drawStyle() {
        const d = this.state.drawing;
        if (!d) {
            return "display:none;";
        }
        const x = Math.min(d.x0, d.x1) * 100;
        const y = Math.min(d.y0, d.y1) * 100;
        const w = Math.abs(d.x1 - d.x0) * 100;
        const h = Math.abs(d.y1 - d.y0) * 100;
        return (
            `left:${x}%; top:${y}%; width:${w}%; height:${h}%;` +
            ` border:2px dashed #3B82F6; background:rgba(59,130,246,0.10);`
        );
    }

    async save() {
        await this.orm.call(
            "invoice.ocr.document", "save_template_zones",
            [this.docId, this.state.zones]
        );
        this.notification.add("Plantilla guardada", { type: "success" });
        this.action.doAction({ type: "ir.actions.act_window_close" });
    }
}
TemplateEditor.template = "invoice_ocr.TemplateEditor";
registry.category("actions").add("invoice_ocr_template_editor", TemplateEditor);
