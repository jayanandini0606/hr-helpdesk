"""
AI-Powered HR Helpdesk — Streamlit Application.
Provides an interactive, role-based localhost experience with separate
Employee and HR/Admin portals, instant AI classification, grounded citations,
sensitive case routing, and SLA tracking.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone
import streamlit as st
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database import query_all, query_one, get_db_path
from src.init_db import init_database
from src.generate_master_data import generate_master_data, CATEGORIES
from src.ticket_service import (
    create_ticket, get_ticket, add_ticket_message,
    reassign_ticket, update_ticket_status, list_tickets,
    get_admin_dashboard_metrics, seed_demo_scenarios
)
from src.policy_retrieval import get_all_policies_summary, get_current_iso_time


# --------------------------------------------------
# Page Configuration & Theme
# --------------------------------------------------
st.set_page_config(
    page_title="AI-Powered HR Helpdesk",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for modern enterprise aesthetic
st.markdown("""
<style>
    .main-header {
        font-size: 1.8rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 0.95rem;
        color: #64748b;
        margin-bottom: 1.25rem;
    }
    .metric-box {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.85rem;
        text-align: center;
    }
    .internal-note-box {
        background-color: #fefce8;
        border: 1px solid #fef08a;
        border-left: 5px solid #eab308;
        padding: 0.85rem;
        border-radius: 6px;
        margin-bottom: 0.75rem;
    }
    .restricted-box {
        background-color: #f8fafc;
        border: 1px solid #cbd5e1;
        border-left: 4px solid #3b82f6;
        padding: 0.85rem;
        border-radius: 6px;
        margin-bottom: 1rem;
    }
    .citation-box {
        background-color: #eff6ff;
        border: 1px solid #bfdbfe;
        border-left: 4px solid #2563eb;
        padding: 0.75rem;
        border-radius: 6px;
        margin-bottom: 0.5rem;
    }
    .sensitive-alert {
        background-color: #fef2f2;
        border: 1px solid #fecaca;
        border-left: 4px solid #ef4444;
        padding: 0.75rem;
        border-radius: 6px;
        margin-bottom: 0.75rem;
    }
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------
# Auto-Initialize Database If Missing
# --------------------------------------------------
def ensure_database_ready():
    db_file = get_db_path()
    if not db_file.exists() or db_file.stat().st_size == 0:
        with st.spinner("Initializing database and generating master policy data..."):
            init_database(db_file)
            generate_master_data(db_path=db_file)
            st.success("Database initialized successfully with 100 employees and 20 policies!")

ensure_database_ready()


# --------------------------------------------------
# Sidebar: Role Selection & Persona Switching
# --------------------------------------------------
st.sidebar.markdown("### 🛡️ Enterprise HR Helpdesk")
st.sidebar.caption("AI-Powered Resolution & SLA Engine")

portal_mode = st.sidebar.radio(
    "Select Portal Workspace:",
    ["👤 Employee Self-Service", "📊 HR / Admin Operations", "📜 Policy & Knowledge Hub"],
    index=0
)

# Fetch employees for persona switching
employees_raw = query_all("SELECT employee_id, full_name, department_id, audience FROM Employee ORDER BY employee_id ASC LIMIT 50")
emp_dict = {f"{e['full_name']} ({e['employee_id']})": e['employee_id'] for e in employees_raw}

if portal_mode == "👤 Employee Self-Service":
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 👤 Employee Persona")
    # Default to EMP-000006
    default_emp_idx = 5 if len(employees_raw) > 5 else 0
    selected_emp_label = st.sidebar.selectbox("Active Employee Identity:", list(emp_dict.keys()), index=default_emp_idx)
    active_emp_id = emp_dict[selected_emp_label]
    active_role = "Employee"
else:
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 🛡️ Staff Persona")
    active_role = st.sidebar.selectbox("Administrative Role:", ["HR Partner", "IT/Operations Partner", "Admin"], index=0)
    active_emp_id = "EMP-000001" if active_role != "IT/Operations Partner" else "EMP-000002"

st.sidebar.markdown("---")
with st.sidebar.expander("⚡ Demo Management Tools"):
    if st.button("Seed 6 Interview Scenarios"):
        results = seed_demo_scenarios()
        st.success(f"Seeded {len(results)} interview demo scenarios!")
        st.rerun()

    if st.button("Reset Master Database"):
        generate_master_data()
        st.success("Master database reset with 100% integrity!")
        st.rerun()


# ==================================================
# 1. EMPLOYEE PORTAL WORKSPACE
# ==================================================
if portal_mode == "👤 Employee Self-Service":
    # Load Employee details
    emp_info = query_one("""
        SELECT e.*, d.department_name
        FROM Employee e
        LEFT JOIN Department d ON e.department_id = d.department_id
        WHERE e.employee_id = ?
    """, (active_emp_id,)) or {"full_name": "Employee", "employee_id": active_emp_id, "department_name": "General", "employment_status": "Active"}

    st.markdown(f"<div class='main-header'>Welcome, {emp_info['full_name']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='sub-header'>Employee ID: <strong>{emp_info['employee_id']}</strong> &bull; Department: <strong>{emp_info['department_name']}</strong> &bull; Status: <span style='color:green;'>{emp_info['employment_status']}</span></div>", unsafe_allow_html=True)

    # Isolated metrics for this employee
    emp_tickets = list_tickets(filters={"employee_id": active_emp_id, "limit": 1000})
    total_emp = len(emp_tickets)
    open_emp = sum(1 for t in emp_tickets if t["status"] in ("Open", "In_Progress", "Awaiting_Employee"))
    resolved_emp = sum(1 for t in emp_tickets if t["status"] in ("Resolved", "Closed"))

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Requests Submitted", total_emp)
    c2.metric("Active / In Review", open_emp)
    c3.metric("Resolved Cases", resolved_emp)

    # Sub-tabs for Employee: My Requests & New Request
    emp_tab1, emp_tab2 = st.tabs(["📋 My Submitted Requests", "✍️ Submit New HR Request"])

    with emp_tab2:
        st.markdown("#### Submit a New HR Request")
        st.caption("Routine inquiries receive instant grounded answers citing verified policies. Sensitive cases are routed securely to specialist queues.")

        with st.form("new_request_form", clear_on_submit=True):
            subj = st.text_input("Subject:", placeholder="e.g., How do I submit medical insurance claims?")
            cat_options = ["(Auto-Detect by AI)"] + [c[1] for c in CATEGORIES]
            cat_selected = st.selectbox("Category (Optional):", cat_options)
            desc = st.text_area("Detailed Request Description:", placeholder="Please provide specific details regarding your inquiry...", height=120)

            submitted = st.form_submit_button("Submit Request &rarr;", type="primary")
            if submitted:
                if not subj or not desc:
                    st.error("Please enter both a subject and a description.")
                else:
                    user_cat_id = None
                    if cat_selected != "(Auto-Detect by AI)":
                        user_cat_id = next((c[0] for c in CATEGORIES if c[1] == cat_selected), None)

                    with st.spinner("Classifying request, evaluating policies, and calculating SLAs..."):
                        res = create_ticket(
                            employee_id=active_emp_id,
                            subject=subj,
                            description=desc,
                            user_category_id=user_cat_id
                        )
                        st.success(f"Ticket {res['ticket_id']} submitted successfully! Status: {res['status']}")
                        st.session_state["selected_employee_ticket_id"] = res["ticket_id"]
                        st.rerun()

    with emp_tab1:
        st.markdown("#### My Tickets History")
        
        # Search & Filter
        fc1, fc2, fc3 = st.columns([2, 1, 1])
        search_kw = fc1.text_input("🔍 Search My Tickets:", placeholder="Filter by subject or keyword...")
        status_flt = fc2.selectbox("Filter Status:", ["All", "Open", "In_Progress", "Awaiting_Employee", "Resolved", "Closed"])
        prio_flt = fc3.selectbox("Filter Priority:", ["All", "Critical", "High", "Medium", "Low"])

        # Apply filters
        filtered_emp_tickets = emp_tickets
        if search_kw:
            kw = search_kw.lower()
            filtered_emp_tickets = [t for t in filtered_emp_tickets if kw in t["subject"].lower() or kw in t["ticket_id"].lower()]
        if status_flt != "All":
            filtered_emp_tickets = [t for t in filtered_emp_tickets if t["status"] == status_flt]
        if prio_flt != "All":
            filtered_emp_tickets = [t for t in filtered_emp_tickets if t["priority"] == prio_flt]

        if not filtered_emp_tickets:
            st.info("No tickets match your filter criteria.")
        else:
            table_data = []
            for t in filtered_emp_tickets:
                sens_text = "🔒 Sensitive" if t["sensitive_flag"] == 1 else "Standard"
                table_data.append({
                    "Ticket ID": t["ticket_id"],
                    "Subject": t["subject"],
                    "Category": t["category_name"],
                    "Priority": t["priority"],
                    "Status": t["status"],
                    "Sensitivity": sens_text,
                    "Submitted": t["created_at"][:16].replace("T", " ")
                })
            
            df_display = pd.DataFrame(table_data)
            st.dataframe(df_display, use_container_width=True, hide_index=True)

            # Ticket Detail Inspector
            st.markdown("---")
            st.markdown("#### 🔍 Inspect Ticket Details")
            t_ids = [t["ticket_id"] for t in filtered_emp_tickets]
            
            selected_t_id = st.selectbox(
                "Select a Ticket to View Conversation & Citations:",
                t_ids,
                index=0 if "selected_employee_ticket_id" not in st.session_state or st.session_state["selected_employee_ticket_id"] not in t_ids else t_ids.index(st.session_state["selected_employee_ticket_id"])
            )

            if selected_t_id:
                bundle = get_ticket(selected_t_id)
                t_data = bundle["ticket"]
                
                # Ticket isolation assertion
                if t_data["employee_id"] != active_emp_id:
                    st.error("Access Denied: You cannot view tickets belonging to another employee.")
                else:
                    st.markdown(f"### Ticket {t_data['ticket_id']} — {t_data['subject']}")
                    
                    mc1, mc2, mc3, mc4 = st.columns(4)
                    mc1.write(f"**Status:** `{t_data['status']}`")
                    mc2.write(f"**Priority:** `{t_data['priority']}`")
                    mc3.write(f"**Category:** {t_data['category_name']}")
                    mc4.write(f"**Queue:** {t_data.get('category_queue', 'HR-General')}")

                    if t_data["sensitive_flag"] == 1:
                        st.markdown("<div class='sensitive-alert'>🔒 <strong>Confidential Handling:</strong> This ticket is assigned to specialist review. AI automatic resolution is disabled.</div>", unsafe_allow_html=True)

                    # Conversation Thread (Strictly strip internal notes for employee)
                    st.markdown("##### 💬 Conversation History")
                    for msg in bundle["messages"]:
                        # Strict privacy: never display internal notes to employee
                        if msg["message_text"].startswith("[INTERNAL NOTE]"):
                            continue

                        sender_icon = "👤" if msg["sender_type"] == "Employee" else ("🤖" if msg["sender_type"] == "Assistant" else "👔")
                        with st.chat_message(name=msg["sender_type"].lower(), avatar=sender_icon):
                            st.write(f"**{msg['sender_type']}** ({msg['message_type']}) — *{msg['created_at'][:16].replace('T', ' ')}*")
                            st.write(msg["message_text"])

                    # Grounded Citations
                    if bundle["citations"]:
                        st.markdown("##### 📚 Official Policy Sources Cited")
                        for cit in bundle["citations"]:
                            st.markdown(f"""
                            <div class='citation-box'>
                                <strong>{cit['policy_title']}</strong> (Version {cit['version_number']})<br>
                                <small>Policy ID: <code>{cit['policy_id']}</code> | Version ID: <code>{cit['version_id']}</code></small><br>
                                <em>"{cit['snippet']}"</em>
                            </div>
                            """, unsafe_allow_html=True)

                    # Post Clarification Form
                    st.markdown("##### ✍️ Send Reply / Clarification")
                    with st.form(f"reply_form_{selected_t_id}", clear_on_submit=True):
                        reply_txt = st.text_area("Your Message:", placeholder="Type any clarification or reply here...", height=80)
                        if st.form_submit_button("Send Reply"):
                            if reply_txt.strip():
                                add_ticket_message(
                                    ticket_id=selected_t_id,
                                    sender_type="Employee",
                                    message_text=reply_txt.strip(),
                                    message_type="Clarification"
                                )
                                st.success("Message sent!")
                                st.rerun()


# ==================================================
# 2. HR / ADMIN OPERATIONS WORKSPACE
# ==================================================
elif portal_mode == "📊 HR / Admin Operations":
    st.markdown("<div class='main-header'>📊 HR Helpdesk Administration &amp; SLA Dashboard</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='sub-header'>Logged in as: <strong>{active_role}</strong> ({active_emp_id}) &bull; Real-time Queue Triage &amp; SLA Compliance</div>", unsafe_allow_html=True)

    metrics = get_admin_dashboard_metrics()

    # 8-KPI Operational Metrics Row
    k1, k2, k3, k4, k5, k6, k7, k8 = st.columns(8)
    k1.metric("Total", metrics["total_tickets"])
    k2.metric("Open", metrics["open_tickets"])
    k3.metric("In-Progress", metrics["in_progress_tickets"])
    k4.metric("Resolved", metrics["resolved_tickets"])
    k5.metric("Sensitive", metrics["sensitive_count"])
    k6.metric("Escalated", metrics["escalated_count"])
    k7.metric("Overdue", metrics["overdue_count"])
    k8.metric("SLA Rate", f"{metrics['sla_compliance_rate']}%")

    st.markdown("---")

    # Multi-Filter Toolbar
    st.markdown("#### 🔍 Filter & Triage Queue")
    f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns(5)
    
    st_status = f_col1.selectbox("Status:", ["All", "Open", "In_Progress", "Awaiting_Employee", "Resolved", "Closed"])
    st_cat = f_col2.selectbox("Category:", ["All"] + [c[1] for c in CATEGORIES])
    st_prio = f_col3.selectbox("Priority:", ["All", "Critical", "High", "Medium", "Low"])
    st_queue = f_col4.selectbox("Queue:", ["All", "Benefits", "Leave", "Payroll", "Onboarding", "HR-Confidential", "IT-Support", "HR-General"])
    st_sens = f_col5.selectbox("Sensitivity:", ["All", "Sensitive Only", "Standard Only"])

    st_search = st.text_input("Search tickets by ID, employee name, or subject:", placeholder="Type search term...")

    # Build filter dict
    filters = {}
    if st_status != "All":
        filters["status"] = st_status
    if st_cat != "All":
        filters["category_id"] = next(c[0] for c in CATEGORIES if c[1] == st_cat)
    if st_prio != "All":
        filters["priority"] = st_prio
    if st_queue != "All":
        filters["assigned_queue"] = st_queue
    if st_sens == "Sensitive Only":
        filters["sensitive_flag"] = 1
    elif st_sens == "Standard Only":
        filters["sensitive_flag"] = 0
    if st_search:
        filters["search"] = st_search

    tickets = list_tickets(filters=filters)
    st.caption(f"Showing {len(tickets)} operational ticket(s)")

    if not tickets:
        st.info("No tickets match the selected filters.")
    else:
        # Display operational table
        t_data_rows = []
        for t in tickets:
            sens_badge = "🔒 Sensitive" if t["sensitive_flag"] == 1 else "Standard"
            overdue_badge = "⚠️ OVERDUE" if t.get("is_overdue") else ("✓ Met" if t.get("resolution_met") == 1 else "On Schedule")
            t_data_rows.append({
                "Ticket ID": t["ticket_id"],
                "Employee": f"{t['employee_name']} ({t['employee_id']})",
                "Subject": t["subject"],
                "Category": t["category_name"],
                "Priority": t["priority"],
                "Sensitive": sens_badge,
                "Queue": t.get("assigned_queue") or "Unassigned",
                "Status": t["status"],
                "SLA Target": overdue_badge,
                "Created Date": t["created_at"][:16].replace("T", " ")
            })
        st.dataframe(pd.DataFrame(t_data_rows), use_container_width=True, hide_index=True)

        # Ticket Management & Escalation Workspace
        st.markdown("---")
        st.markdown("### 🛠️ Ticket Management & Escalation Console")
        
        all_ids = [t["ticket_id"] for t in tickets]
        target_id = st.selectbox("Select Ticket ID for Detailed Review & Workflow Action:", all_ids)

        if target_id:
            bundle = get_ticket(target_id)
            t_item = bundle["ticket"]

            left_col, right_col = st.columns([3, 2])

            with left_col:
                st.markdown(f"#### Ticket `{t_item['ticket_id']}`: {t_item['subject']}")
                
                # Restricted Employee Master Data (HR/Admin Only)
                st.markdown(f"""
                <div class='restricted-box'>
                    <strong>🔒 Restricted Staff View — Employee Master Data</strong><br>
                    Employee: <strong>{t_item['employee_name']}</strong> ({t_item['employee_id']})<br>
                    Department: {t_item.get('department_name', 'Human Resources')} &bull; Status: {t_item.get('employment_status', 'Active')} &bull; Manager: {t_item.get('manager_id', 'None')}
                </div>
                """, unsafe_allow_html=True)

                if t_item["sensitive_flag"] == 1:
                    st.markdown(f"<div class='sensitive-alert'>🔒 <strong>Confidential Escalation Active:</strong> Reason: {t_item.get('issue_type', 'Restricted')}. Automatic AI resolution prohibited.</div>", unsafe_allow_html=True)

                # Full Conversation Thread (Including Internal Notes with distinctive styling)
                st.markdown("##### 💬 Case Messages & Investigation History")
                for msg in bundle["messages"]:
                    is_internal = msg["message_text"].startswith("[INTERNAL NOTE]")
                    if is_internal:
                        clean_note = msg["message_text"].replace("[INTERNAL NOTE]", "").strip()
                        st.markdown(f"""
                        <div class='internal-note-box'>
                            <strong>🔒 CONFIDENTIAL INTERNAL NOTE (Staff Only)</strong> &bull; <em>{msg['created_at'][:16].replace('T', ' ')}</em><br>
                            {clean_note}
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        avatar = "👤" if msg["sender_type"] == "Employee" else ("🤖" if msg["sender_type"] == "Assistant" else "👔")
                        with st.chat_message(name=msg["sender_type"].lower(), avatar=avatar):
                            st.write(f"**{msg['sender_type']}** ({msg['message_type']}) — *{msg['created_at'][:16].replace('T', ' ')}*")
                            st.write(msg["message_text"])

                # Grounded Citations
                if bundle["citations"]:
                    st.markdown("##### 📚 Applicable Policy Citations")
                    for cit in bundle["citations"]:
                        st.markdown(f"""
                        <div class='citation-box'>
                            <strong>{cit['policy_title']}</strong> (Version {cit['version_number']})<br>
                            <small>Policy ID: {cit['policy_id']} | Article: {cit['article_id']}</small><br>
                            <em>"{cit['snippet']}"</em>
                        </div>
                        """, unsafe_allow_html=True)

                # Case Communication / Internal Notes Form
                st.markdown("##### ✍️ Post Case Message / Internal Staff Note")
                with st.form(f"admin_msg_{target_id}", clear_on_submit=True):
                    comm_type = st.radio("Message Destination:", ["💬 Reply to Employee (Public)", "🔒 Confidential Internal Note (Staff Only)"], horizontal=True)
                    admin_msg_text = st.text_area("Content:", placeholder="Enter response to employee or internal case investigation note...", height=90)
                    if st.form_submit_button("Submit Entry"):
                        if admin_msg_text.strip():
                            is_int = "Confidential Internal Note" in comm_type
                            final_msg = f"[INTERNAL NOTE] {admin_msg_text.strip()}" if is_int else admin_msg_text.strip()
                            add_ticket_message(
                                ticket_id=target_id,
                                sender_type="HR",
                                message_text=final_msg,
                                message_type="Clarification"
                            )
                            st.success("Case record updated!")
                            st.rerun()

            with right_col:
                st.markdown("#### ⚙️ Operations & SLA Controls")

                # SLA Tracking Box
                if bundle["sla"]:
                    sla_info = bundle["sla"]
                    sla_eval = bundle["sla_status"]
                    st.markdown(f"""
                    <div style='background: white; border: 1px solid #cbd5e1; border-radius: 8px; padding: 0.85rem; margin-bottom: 1rem;'>
                        <strong>⏱️ SLA Performance</strong><br>
                        Policy: <code>{sla_info['policy_name']}</code><br>
                        Response Due: {sla_info['response_due_at'][:16].replace('T', ' ')} (Met: {'✓' if sla_info['response_met']==1 else 'Pending'})<br>
                        Resolution Due: {sla_info['resolution_due_at'][:16].replace('T', ' ')}<br>
                        Status: {'<span style=\"color:red; font-weight:bold;\">⚠️ OVERDUE</span>' if sla_eval.get('is_resolution_overdue') else '<span style=\"color:green;\">On Schedule</span>'}
                    </div>
                    """, unsafe_allow_html=True)

                # Reassign Queue Form
                with st.expander("🔄 Reassign Ticket Queue"):
                    with st.form(f"reassign_{target_id}"):
                        new_q = st.selectbox("Assign to Queue:", ["Benefits", "Leave", "Payroll", "Onboarding", "HR-Confidential", "IT-Support", "HR-General"])
                        reassign_reason = st.text_input("Reassignment Rationale:", placeholder="e.g. Requires specialized payroll investigation")
                        if st.form_submit_button("Reassign Queue"):
                            if reassign_reason.strip():
                                reassign_ticket(target_id, new_q, active_emp_id, reassign_reason.strip())
                                st.success(f"Ticket reassigned to {new_q}!")
                                st.rerun()

                # Status Transition & Outcome Form
                with st.expander("🏁 Update Status & Resolution Outcome"):
                    with st.form(f"status_{target_id}"):
                        new_st = st.selectbox("New Status:", ["Open", "In_Progress", "Awaiting_Employee", "Resolved", "Closed"], index=["Open", "In_Progress", "Awaiting_Employee", "Resolved", "Closed"].index(t_item["status"]))
                        new_outcome = st.selectbox("Resolution Outcome (if resolving):", ["", "Answered", "Escalated", "Rejected", "Unresolved"])
                        res_summary = st.text_input("Resolution Summary:", placeholder="e.g. Employee provided clarification and policy guidance explained.")
                        st_reason = st.text_input("Status Change Reason:", value="Reviewed by HR Partner")
                        if st.form_submit_button("Update Status"):
                            update_ticket_status(
                                ticket_id=target_id,
                                new_status=new_st,
                                reason=st_reason,
                                resolution_outcome=new_outcome or None,
                                resolution_summary=res_summary or None
                            )
                            st.success(f"Ticket status updated to {new_st}!")
                            st.rerun()

                # Audit History Trail
                with st.expander("📜 Event Audit Trail"):
                    for evt in bundle["events"]:
                        st.write(f"• **{evt.get('old_status') or 'Start'} &rarr; {evt['new_status']}**")
                        st.caption(f"{evt['reason']} ({evt['occurred_at'][:16].replace('T', ' ')})")


# ==================================================
# 3. POLICY & KNOWLEDGE HUB WORKSPACE
# ==================================================
else:
    st.markdown("<div class='main-header'>📜 Policy Hub &amp; Knowledge Base</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-header'>Browse version-controlled HR policies, effective dates, draft versions, and knowledge articles.</div>", unsafe_allow_html=True)

    as_of = st.date_input("Query As-Of Effective Date:", value=datetime.now(timezone.utc).date())
    as_of_str = as_of.strftime("%Y-%m-%d")

    policies = get_all_policies_summary(as_of_date=as_of_str)
    st.caption(f"Showing {len(policies)} policies evaluated as of {as_of_str}")

    for p in policies:
        with st.expander(f"{p['title']} ({p['category_name']}) — Effective: {p.get('effective_from', 'N/A')}"):
            st.write(f"**Policy ID:** `{p['policy_id']}` &bull; **Owner Department:** `{p['owner_department_id']}` &bull; **Audience:** `{p['audience']}`")
            st.write(f"**Selected Version:** Version `{p['version_number']}` (Status: `{p['version_status']}`)")
            st.markdown(f"**Policy Text:**\n{p['policy_text']}")

            # Knowledge articles
            articles = query_all("""
                SELECT * FROM KnowledgeArticle WHERE version_id = ?
            """, (p["version_id"],))
            if articles:
                st.markdown(f"**Published Guidance Articles ({len(articles)}):**")
                for a in articles:
                    st.write(f"• **{a['title']}** (`{a['article_id']}`): {a['snippet']}")
