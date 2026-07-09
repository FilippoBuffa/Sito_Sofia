import os
from flask import render_template, redirect, url_for, flash, request, abort, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models import TestRequest, Comment
from app.models.user import User as UserModel
from app.models.part_group import MANUFACTURING_PROCESS_CHOICES
from app.email_service import (
    send_awaiting_parts, send_request_returned, send_request_closed,
    send_parts_received_notification,
)
from datetime import datetime, timezone, date
from . import bp


ALLOWED_EXTENSIONS = {"pdf", "xlsx", "xls", "csv", "zip", "docx", "doc", "png", "jpg", "jpeg"}


def require_engineer(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_engineer:
            abort(403)
        return f(*args, **kwargs)

    return decorated


def _engineer_service_ids():
    return [s.id for s in current_user.services]


@bp.route("/dashboard")
@login_required
@require_engineer
def dashboard():
    service_ids = _engineer_service_ids()

    submitted = (
        TestRequest.query.filter(
            TestRequest.service_id.in_(service_ids),
            TestRequest.status == "submitted",
        ).order_by(TestRequest.date_submitted.asc()).all()
    )
    awaiting_parts = (
        TestRequest.query.filter(
            TestRequest.service_id.in_(service_ids),
            TestRequest.status == "awaiting_parts",
        ).order_by(TestRequest.date_submitted.asc()).all()
    )
    parts_shipped = (
        TestRequest.query.filter(
            TestRequest.service_id.in_(service_ids),
            TestRequest.status == "parts_shipped",
        ).order_by(TestRequest.date_shipped.asc()).all()
    )
    in_progress = (
        TestRequest.query.filter(
            TestRequest.service_id.in_(service_ids),
            TestRequest.status == "in_progress",
        ).order_by(TestRequest.date_submitted.asc()).all()
    )

    search_query = request.args.get("q", "").strip()
    closed_query = (
        TestRequest.query
        .join(UserModel, TestRequest.requester_id == UserModel.id)
        .filter(TestRequest.service_id.in_(service_ids), TestRequest.status == "closed")
    )
    if search_query:
        term = f"%{search_query}%"
        closed_query = closed_query.filter(db.or_(
            TestRequest.tr_number.ilike(term),
            UserModel.email.ilike(term),
            UserModel.first_name.ilike(term),
            UserModel.last_name.ilike(term),
        ))
    closed = closed_query.order_by(TestRequest.date_closed.desc()).all()

    return render_template(
        "engineer/dashboard.html",
        submitted=submitted,
        awaiting_parts=awaiting_parts,
        parts_shipped=parts_shipped,
        in_progress=in_progress,
        closed=closed,
        search_query=search_query,
    )


@bp.route("/request/<int:request_id>", methods=["GET", "POST"])
@login_required
@require_engineer
def request_detail(request_id):
    req = TestRequest.query.get_or_404(request_id)
    if req.service_id not in _engineer_service_ids():
        abort(403)

    if request.method == "POST":
        text = request.form.get("comment_text", "").strip()
        if text:
            comment = Comment(request_id=req.id, author_id=current_user.id, text=text)
            db.session.add(comment)
            db.session.commit()
            flash("Comment added.", "success")
        return redirect(url_for("engineer.request_detail", request_id=request_id))

    comments = req.comments.all()
    part_groups = req.part_groups.all()
    attachments = req.attachments.all()
    return render_template(
        "engineer/request_detail.html",
        req=req,
        comments=comments,
        part_groups=part_groups,
        attachments=attachments,
        manufacturing_process_choices=MANUFACTURING_PROCESS_CHOICES,
        today=date.today(),
    )


@bp.route("/request/<int:request_id>/accept", methods=["POST"])
@login_required
@require_engineer
def accept(request_id):
    req = TestRequest.query.get_or_404(request_id)
    if req.service_id not in _engineer_service_ids():
        abort(403)
    if req.status != "submitted":
        flash(f"Request {req.tr_number} is no longer in Submitted status.", "warning")
        return redirect(url_for("engineer.dashboard"))

    new_tr = request.form.get("tr_number", "").strip()
    if not new_tr:
        flash("Please provide a TR number.", "warning")
        return redirect(url_for("engineer.request_detail", request_id=request_id))
    if new_tr != req.tr_number and TestRequest.query.filter_by(tr_number=new_tr).first():
        flash(f"TR number '{new_tr}' is already in use by another request.", "danger")
        return redirect(url_for("engineer.request_detail", request_id=request_id))

    req.tr_number = new_tr
    req.status = "awaiting_parts"
    req.assigned_engineer_id = current_user.id
    db.session.commit()

    send_awaiting_parts(req)
    flash(f"Request {req.tr_number} accepted — client notified to ship parts.", "success")
    return redirect(url_for("engineer.dashboard"))


@bp.route("/request/<int:request_id>/parts-received", methods=["POST"])
@login_required
@require_engineer
def parts_received(request_id):
    req = TestRequest.query.get_or_404(request_id)
    if req.service_id not in _engineer_service_ids():
        abort(403)
    if req.status != "parts_shipped":
        flash(f"Request {req.tr_number} parts have not been marked as shipped yet.", "warning")
        return redirect(url_for("engineer.request_detail", request_id=request_id))

    est_delivery_str = request.form.get("estimated_delivery", "").strip()
    estimated_delivery = None
    if est_delivery_str:
        try:
            estimated_delivery = date.fromisoformat(est_delivery_str)
        except ValueError:
            flash("Invalid estimated delivery date.", "warning")
            return redirect(url_for("engineer.request_detail", request_id=request_id))

    req.status = "in_progress"
    req.date_parts_received = datetime.now(timezone.utc)
    req.estimated_delivery = estimated_delivery
    db.session.commit()

    send_parts_received_notification(req)
    flash(f"Parts received — {req.tr_number} is now In Progress.", "success")
    return redirect(url_for("engineer.dashboard"))


@bp.route("/request/<int:request_id>/return", methods=["POST"])
@login_required
@require_engineer
def return_request(request_id):
    req = TestRequest.query.get_or_404(request_id)
    if req.service_id not in _engineer_service_ids():
        abort(403)
    if req.status not in ("submitted", "awaiting_parts", "in_progress"):
        flash(f"Request {req.tr_number} cannot be returned (current status: {req.status_label}).", "warning")
        return redirect(url_for("engineer.dashboard"))

    note = request.form.get("return_note", "").strip()
    if not note:
        flash("Please provide a reason for returning the request.", "warning")
        return redirect(url_for("engineer.request_detail", request_id=request_id))

    req.status = "returned"
    comment = Comment(request_id=req.id, author_id=current_user.id, text=f"[Returned] {note}")
    db.session.add(comment)
    db.session.commit()

    send_request_returned(req, note)
    flash(f"Request {req.tr_number} returned to client.", "warning")
    return redirect(url_for("engineer.dashboard"))


@bp.route("/request/<int:request_id>/close", methods=["POST"])
@login_required
@require_engineer
def close_request(request_id):
    req = TestRequest.query.get_or_404(request_id)
    if req.service_id not in _engineer_service_ids():
        abort(403)
    if req.status != "in_progress":
        flash(f"Request {req.tr_number} cannot be closed (current status: {req.status_label}).", "warning")
        return redirect(url_for("engineer.dashboard"))

    file = request.files.get("result_file")
    if not file or file.filename == "":
        flash("Please upload a result file to close the request.", "warning")
        return redirect(url_for("engineer.request_detail", request_id=request_id))

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        flash("File type not allowed.", "danger")
        return redirect(url_for("engineer.request_detail", request_id=request_id))

    filename = secure_filename(f"{req.tr_number}_{file.filename}")
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    file.save(os.path.join(upload_folder, filename))

    req.result_file_path = filename
    req.result_original_filename = file.filename
    req.status = "closed"
    req.date_closed = datetime.now(timezone.utc)

    closing_note = request.form.get("closing_note", "").strip()
    if closing_note:
        comment = Comment(request_id=req.id, author_id=current_user.id, text=f"[Closed] {closing_note}")
        db.session.add(comment)

    db.session.commit()
    send_request_closed(req)
    flash(f"Request {req.tr_number} closed successfully.", "success")
    return redirect(url_for("engineer.dashboard"))


@bp.route("/request/<int:request_id>/delete", methods=["POST"])
@login_required
@require_engineer
def delete_request(request_id):
    req = TestRequest.query.get_or_404(request_id)
    if req.service_id not in _engineer_service_ids():
        abort(403)

    tr_number = req.tr_number
    _delete_request_files(req)
    db.session.delete(req)
    db.session.commit()
    flash(f"Request {tr_number} permanently deleted.", "success")
    return redirect(url_for("engineer.dashboard"))


def _delete_request_files(req):
    if req.result_file_path:
        path = os.path.join(current_app.config["UPLOAD_FOLDER"], req.result_file_path)
        if os.path.exists(path):
            os.remove(path)
    for att in req.attachments.all():
        path = os.path.join(current_app.config["ATTACHMENT_FOLDER"], att.filename)
        if os.path.exists(path):
            os.remove(path)


@bp.route("/download/<int:request_id>")
@login_required
def download_result(request_id):
    req = TestRequest.query.get_or_404(request_id)
    if current_user.is_client:
        if req.requester_id != current_user.id or not req.can_be_downloaded:
            abort(403)
    elif current_user.is_engineer:
        if req.service_id not in _engineer_service_ids():
            abort(403)
    if not req.result_file_path:
        abort(404)
    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        req.result_file_path,
        as_attachment=True,
        download_name=req.result_original_filename or req.result_file_path,
    )


@bp.route("/attachment/<int:attachment_id>")
@login_required
def download_attachment(attachment_id):
    from app.models.attachment import RequestAttachment
    att = RequestAttachment.query.get_or_404(attachment_id)
    req = att.request
    if current_user.is_client and req.requester_id != current_user.id:
        abort(403)
    if current_user.is_engineer and req.service_id not in _engineer_service_ids():
        abort(403)
    return send_from_directory(
        current_app.config["ATTACHMENT_FOLDER"],
        att.filename,
        as_attachment=True,
        download_name=att.original_filename,
    )
