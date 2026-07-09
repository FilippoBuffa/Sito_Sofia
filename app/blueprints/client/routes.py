import os
from flask import render_template, redirect, url_for, flash, request, abort, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models import TestRequest, PartGroup, Comment, RequestAttachment
from app.models.user import TestService
from app.models.part_group import GROUP_LETTERS, MANUFACTURING_PROCESS_CHOICES, GROUP_TYPE_CHOICES, LOCATION_CHOICES, VALVE_TYPES
from app.models.request import generate_tr_number
from app.email_service import (
    send_new_request_notification, send_request_resubmitted,
    send_parts_shipped_notification,
)
from datetime import date, datetime, timezone
from . import bp


def require_client(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_client:
            abort(403)
        return f(*args, **kwargs)

    return decorated


@bp.route("/dashboard")
@login_required
@require_client
def dashboard():
    active_statuses = ("submitted", "returned", "awaiting_parts", "parts_shipped", "in_progress")
    all_active = (
        TestRequest.query.filter(
            TestRequest.requester_id == current_user.id,
            TestRequest.status.in_(active_statuses),
        ).order_by(TestRequest.date_submitted.desc()).all()
    )
    submitted     = [r for r in all_active if r.status == "submitted"]
    returned      = [r for r in all_active if r.status == "returned"]
    awaiting      = [r for r in all_active if r.status in ("awaiting_parts", "parts_shipped")]
    in_progress   = [r for r in all_active if r.status == "in_progress"]
    closed = (
        TestRequest.query.filter_by(requester_id=current_user.id, status="closed")
        .order_by(TestRequest.date_closed.desc()).all()
    )
    return render_template(
        "client/dashboard.html",
        submitted=submitted,
        returned=returned,
        awaiting=awaiting,
        in_progress=in_progress,
        closed=closed,
    )


@bp.route("/tests")
@login_required
@require_client
def test_catalog():
    services = TestService.query.filter_by(active=True).all()
    return render_template("client/test_catalog.html", services=services)


@bp.route("/new-request/<int:service_id>", methods=["GET", "POST"])
@login_required
@require_client
def new_request(service_id):
    service = TestService.query.get_or_404(service_id)
    if not service.accepting_requests:
        flash(f"{service.name} is not currently accepting new requests.", "warning")
        return redirect(url_for("client.test_catalog"))

    if request.method == "POST":
        error = _validate_request_form()
        if error:
            flash(error, "danger")
            return _render_new_request_form(service, form_data=request.form)

        tr = generate_tr_number()
        while TestRequest.query.filter_by(tr_number=tr).first():
            tr = generate_tr_number()

        test_request = _build_test_request(tr, service)
        db.session.add(test_request)
        db.session.flush()

        _build_part_groups(test_request)
        _save_attachments(test_request)
        db.session.commit()

        send_new_request_notification(test_request)
        flash(f"Request {test_request.tr_number} submitted successfully.", "success")
        return redirect(url_for("client.dashboard"))

    return _render_new_request_form(service)


def _service_fluid(service_name):
    """The fluid is implied by the service name (Air Flow Test -> air, Water Flow Test -> water).
    Returns None for a service whose name doesn't imply a single fluid, leaving fluid a free choice."""
    name = (service_name or "").lower()
    if "air" in name and "water" not in name:
        return "air"
    if "water" in name and "air" not in name:
        return "water"
    return None


def _render_new_request_form(service, form_data=None):
    total_groups = 1
    if form_data:
        try:
            total_groups = max(1, min(10, int(form_data.get("num_groups", 1))))
        except (TypeError, ValueError):
            total_groups = 1
    return render_template(
        "client/new_request.html",
        service=service,
        group_letters=GROUP_LETTERS,
        manufacturing_process_choices=MANUFACTURING_PROCESS_CHOICES,
        group_type_choices=GROUP_TYPE_CHOICES,
        location_choices=LOCATION_CHOICES,
        valve_types=VALVE_TYPES,
        today=date.today().isoformat(),
        form_data=form_data,
        total_groups=total_groups,
        fixed_fluid=_service_fluid(service.name),
    )


@bp.route("/request/<int:request_id>", methods=["GET", "POST"])
@login_required
@require_client
def request_detail(request_id):
    req = TestRequest.query.get_or_404(request_id)
    if req.requester_id != current_user.id:
        abort(403)

    if request.method == "POST":
        text = request.form.get("comment_text", "").strip()
        if text:
            comment = Comment(request_id=req.id, author_id=current_user.id, text=text)
            db.session.add(comment)
            db.session.commit()
            flash("Comment added.", "success")
        return redirect(url_for("client.request_detail", request_id=request_id))

    comments = req.comments.all()
    part_groups = req.part_groups.all()
    attachments = req.attachments.all()
    return render_template(
        "client/request_detail.html",
        req=req,
        comments=comments,
        part_groups=part_groups,
        attachments=attachments,
        manufacturing_process_choices=MANUFACTURING_PROCESS_CHOICES,
    )


@bp.route("/request/<int:request_id>/mark-shipped", methods=["POST"])
@login_required
@require_client
def mark_shipped(request_id):
    req = TestRequest.query.get_or_404(request_id)
    if req.requester_id != current_user.id:
        abort(403)
    if req.status != "awaiting_parts":
        flash(f"Request {req.tr_number} is not in Awaiting Parts status.", "warning")
        return redirect(url_for("client.dashboard"))

    req.status = "parts_shipped"
    req.date_shipped = datetime.now(timezone.utc)
    db.session.commit()

    send_parts_shipped_notification(req)
    flash(f"Parts marked as shipped for {req.tr_number}. The lab has been notified.", "success")
    return redirect(url_for("client.dashboard"))


@bp.route("/request/<int:request_id>/shipping-sheet")
@login_required
@require_client
def shipping_sheet(request_id):
    req = TestRequest.query.get_or_404(request_id)
    if req.requester_id != current_user.id:
        abort(403)
    if req.status not in ("awaiting_parts", "parts_shipped", "in_progress", "closed"):
        abort(403)
    part_groups = req.part_groups.all()
    return render_template("client/shipping_sheet.html", req=req, part_groups=part_groups, today=date.today())


@bp.route("/request/<int:request_id>/edit", methods=["GET", "POST"])
@login_required
@require_client
def edit_request(request_id):
    req = TestRequest.query.get_or_404(request_id)
    if req.requester_id != current_user.id:
        abort(403)
    if req.status != "returned":
        flash(f"Request {req.tr_number} is no longer in Returned status.", "warning")
        return redirect(url_for("client.dashboard"))

    if request.method == "POST":
        error = _validate_request_form()

        need_by_str = request.form.get("need_by_date", "").strip()
        need_by_date = None
        if need_by_str:
            try:
                need_by_date = date.fromisoformat(need_by_str)
            except ValueError:
                error = error or "Invalid 'Need By Date' format."

        # Reflect submitted values on the in-memory object so a validation error never
        # loses what the client typed — nothing is committed unless validation passes.
        req.priority = request.form.get("priority")
        req.need_by_date = need_by_date
        req.location = request.form.get("location") or None
        req.department = request.form.get("department", "").strip() or None
        req.project = request.form.get("project", "").strip() or None
        req.valve_type = request.form.get("valve_type", "").strip() or None
        req.valve_type_other = request.form.get("valve_type_other", "").strip() or None
        req.part_number = request.form.get("part_number", "").strip() or None
        req.report_type = request.form.get("report_type") or None
        req.report_notes = request.form.get("report_notes", "").strip() or None
        req.max_forward_pressure = request.form.get("max_forward_pressure", "").strip() or None
        req.fluid = _service_fluid(req.service.name) or (request.form.get("fluid") or None)
        req.previously_tested = request.form.get("previously_tested") == "yes"
        req.previous_tr_numbers = request.form.get("previous_tr_numbers", "").strip() or None
        req.test_purpose = request.form.get("test_purpose", "").strip() or None
        req.additional_instructions = request.form.get("additional_instructions", "").strip() or None

        if error:
            flash(error, "danger")
            return _render_edit_request_form(req, form_data=request.form)

        req.total_groups = max(1, min(10, int(request.form.get("num_groups", 1))))

        for pg in req.part_groups.all():
            db.session.delete(pg)
        db.session.flush()

        _build_part_groups(req)
        req.status = "submitted"
        db.session.commit()

        send_request_resubmitted(req)
        flash(f"Request {req.tr_number} updated and resubmitted.", "success")
        return redirect(url_for("client.dashboard"))

    return _render_edit_request_form(req)


def _render_edit_request_form(req, form_data=None):
    if form_data:
        try:
            total_groups = max(1, min(10, int(form_data.get("num_groups", 1))))
        except (TypeError, ValueError):
            total_groups = 1
        part_groups = [_FormPartGroupView(GROUP_LETTERS[i]) for i in range(total_groups)]
    else:
        part_groups = req.part_groups.all()
    return render_template(
        "client/edit_request.html",
        req=req,
        part_groups=part_groups,
        group_letters=GROUP_LETTERS,
        manufacturing_process_choices=MANUFACTURING_PROCESS_CHOICES,
        group_type_choices=GROUP_TYPE_CHOICES,
        location_choices=LOCATION_CHOICES,
        valve_types=VALVE_TYPES,
        today=date.today().isoformat(),
        fixed_fluid=_service_fluid(req.service.name),
    )


class _FormPartGroupView:
    """Adapts posted 'group_<letter>_*' fields to look like a PartGroup ORM object,
    so error re-display can reuse the same template/macro used for real PartGroup rows."""

    def __init__(self, letter):
        prefix = f"group_{letter}_"
        f = request.form
        self.group_letter = letter
        self.location = f.get(prefix + "location") or None
        self.valve_type = f.get(prefix + "valve_type", "").strip() or None
        self.valve_type_other = f.get(prefix + "valve_type_other", "").strip() or None
        self.part_number = f.get(prefix + "part_number", "").strip() or None
        self.group_id = f.get(prefix + "group_id", "").strip() or None
        self.quantity = _safe_int(f.get(prefix + "quantity"))
        self.group_type = f.get(prefix + "group_type") or None
        self.manufacturing_process = f.get(prefix + "manufacturing_process") or None
        self.manufacturing_process_other = f.get(prefix + "manufacturing_process_other", "").strip() or None
        inspected_val = f.get(prefix + "inspected")
        self.inspected = True if inspected_val == "yes" else (False if inspected_val == "no" else None)
        self.part_type = f.get(prefix + "part_type", "").strip() or None
        self.vl_part_number = f.get(prefix + "vl_part_number", "").strip() or None
        self.va_number = f.get(prefix + "va_number", "").strip() or None
        self.x_number = f.get(prefix + "x_number", "").strip() or None
        self.material_lab_code = f.get(prefix + "material_lab_code", "").strip() or None
        self.material_prod_code = f.get(prefix + "material_prod_code", "").strip() or None
        self.batch_no = f.get(prefix + "batch_no", "").strip() or None
        self.alternate_batch_no = f.get(prefix + "alternate_batch_no", "").strip() or None
        self.production_location = f.get(prefix + "production_location", "").strip() or None
        mold_date_str = f.get(prefix + "mold_date", "").strip()
        self.mold_date = None
        if mold_date_str:
            try:
                self.mold_date = date.fromisoformat(mold_date_str)
            except ValueError:
                pass
        self.post_cure = f.get(prefix + "post_cure", "").strip() or None
        self.mold_tool_number = f.get(prefix + "mold_tool_number", "").strip() or None
        self.other_description = f.get(prefix + "other_description", "").strip() or None


@bp.route("/request/<int:request_id>/resubmit", methods=["POST"])
@login_required
@require_client
def resubmit(request_id):
    req = TestRequest.query.get_or_404(request_id)
    if req.requester_id != current_user.id:
        abort(403)
    if req.status != "returned":
        flash(f"Request {req.tr_number} is no longer in Returned status.", "warning")
        return redirect(url_for("client.dashboard"))

    req.status = "submitted"
    db.session.commit()
    send_request_resubmitted(req)
    flash(f"Request {req.tr_number} resubmitted.", "success")
    return redirect(url_for("client.dashboard"))


@bp.route("/request/<int:request_id>/delete", methods=["POST"])
@login_required
@require_client
def delete_request(request_id):
    req = TestRequest.query.get_or_404(request_id)
    if req.requester_id != current_user.id:
        abort(403)

    tr_number = req.tr_number
    _delete_request_files(req)
    db.session.delete(req)
    db.session.commit()
    flash(f"Request {tr_number} permanently deleted.", "success")
    return redirect(url_for("client.dashboard"))


def _delete_request_files(req):
    if req.result_file_path:
        path = os.path.join(current_app.config["UPLOAD_FOLDER"], req.result_file_path)
        if os.path.exists(path):
            os.remove(path)
    for att in req.attachments.all():
        path = os.path.join(current_app.config["ATTACHMENT_FOLDER"], att.filename)
        if os.path.exists(path):
            os.remove(path)


def _validate_request_form():
    if request.form.get("priority", "").strip() not in ("high", "medium", "low"):
        return "Please select a priority before submitting."
    try:
        num = int(request.form.get("num_groups", 1))
        if num < 1:
            return "At least one part group is required."
    except ValueError:
        return "Invalid number of groups."
    for letter in GROUP_LETTERS[:max(1, min(10, num))]:
        if not request.form.get(f"group_{letter}_quantity", "").strip():
            return f"Please enter the quantity for Group {letter}."
    return None


def _build_test_request(tr, service):
    need_by_str = request.form.get("need_by_date", "").strip()
    need_by_date = None
    if need_by_str:
        try:
            need_by_date = date.fromisoformat(need_by_str)
        except ValueError:
            pass

    return TestRequest(
        tr_number=tr,
        status="submitted",
        requester_id=current_user.id,
        service_id=service.id,
        priority=request.form.get("priority"),
        need_by_date=need_by_date,
        test_type="Checkvalve Performance",
        location=request.form.get("location") or None,
        department=request.form.get("department", "").strip() or None,
        project=request.form.get("project", "").strip() or None,
        valve_type=request.form.get("valve_type", "").strip() or None,
        valve_type_other=request.form.get("valve_type_other", "").strip() or None,
        part_number=request.form.get("part_number", "").strip() or None,
        report_type=request.form.get("report_type") or None,
        report_notes=request.form.get("report_notes", "").strip() or None,
        max_forward_pressure=request.form.get("max_forward_pressure", "").strip() or None,
        fluid=_service_fluid(service.name) or (request.form.get("fluid") or None),
        previously_tested=request.form.get("previously_tested") == "yes",
        previous_tr_numbers=request.form.get("previous_tr_numbers", "").strip() or None,
        test_purpose=request.form.get("test_purpose", "").strip() or None,
        additional_instructions=request.form.get("additional_instructions", "").strip() or None,
        total_groups=max(1, min(10, int(request.form.get("num_groups", 1)))),
    )


def _build_part_groups(test_request):
    for i in range(test_request.total_groups):
        letter = GROUP_LETTERS[i]
        prefix = f"group_{letter}_"

        mold_date_str = request.form.get(prefix + "mold_date", "").strip()
        mold_date = None
        if mold_date_str:
            try:
                mold_date = date.fromisoformat(mold_date_str)
            except ValueError:
                pass

        inspected_val = request.form.get(prefix + "inspected")
        inspected = True if inspected_val == "yes" else (False if inspected_val == "no" else None)

        pg = PartGroup(
            request_id=test_request.id,
            group_letter=letter,
            location=request.form.get(prefix + "location") or None,
            valve_type=request.form.get(prefix + "valve_type", "").strip() or None,
            valve_type_other=request.form.get(prefix + "valve_type_other", "").strip() or None,
            part_number=request.form.get(prefix + "part_number", "").strip() or None,
            group_id=request.form.get(prefix + "group_id", "").strip() or None,
            quantity=_safe_int(request.form.get(prefix + "quantity")),
            group_type=request.form.get(prefix + "group_type") or None,
            manufacturing_process=request.form.get(prefix + "manufacturing_process") or None,
            manufacturing_process_other=request.form.get(prefix + "manufacturing_process_other", "").strip() or None,
            inspected=inspected,
            part_type=request.form.get(prefix + "part_type", "").strip() or None,
            vl_part_number=request.form.get(prefix + "vl_part_number", "").strip() or None,
            va_number=request.form.get(prefix + "va_number", "").strip() or None,
            x_number=request.form.get(prefix + "x_number", "").strip() or None,
            material_lab_code=request.form.get(prefix + "material_lab_code", "").strip() or None,
            material_prod_code=request.form.get(prefix + "material_prod_code", "").strip() or None,
            batch_no=request.form.get(prefix + "batch_no", "").strip() or None,
            alternate_batch_no=request.form.get(prefix + "alternate_batch_no", "").strip() or None,
            production_location=request.form.get(prefix + "production_location", "").strip() or None,
            mold_date=mold_date,
            post_cure=request.form.get(prefix + "post_cure", "").strip() or None,
            mold_tool_number=request.form.get(prefix + "mold_tool_number", "").strip() or None,
            other_description=request.form.get(prefix + "other_description", "").strip() or None,
        )
        db.session.add(pg)


def _save_attachments(test_request):
    folder = current_app.config["ATTACHMENT_FOLDER"]
    os.makedirs(folder, exist_ok=True)
    max_size = current_app.config["MAX_ATTACHMENT_SIZE"]
    max_count = current_app.config["MAX_ATTACHMENTS"]

    files = request.files.getlist("attachments")
    saved = 0
    for f in files:
        if saved >= max_count:
            break
        if not f or not f.filename:
            continue
        data = f.read()
        if len(data) > max_size:
            flash(f"File '{f.filename}' exceeds 10 MB limit and was skipped.", "warning")
            continue
        safe_name = secure_filename(f"att_{test_request.id}_{saved}_{f.filename}")
        with open(os.path.join(folder, safe_name), "wb") as out:
            out.write(data)
        att = RequestAttachment(
            request_id=test_request.id,
            filename=safe_name,
            original_filename=f.filename,
            file_size=len(data),
        )
        db.session.add(att)
        saved += 1


def _safe_int(val):
    try:
        return int(val)
    except (TypeError, ValueError):
        return None
