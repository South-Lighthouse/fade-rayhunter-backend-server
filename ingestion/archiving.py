"""
Shared move-to-archive / reclaim-space mechanics, used by both `ingestion`
(raw QMDL/GPS/log uploads) and `radio` (generated PCAPs).

The flow this supports, by design, is fully manual and sequential:
  1. An admin marks eligible rows as archived -- this MOVES the file out of
     its live directory (UPLOAD_ROOT / RADIO_PCAP_ROOT) into ARCHIVE_ROOT.
  2. The admin pulls everything out of ARCHIVE_ROOT themselves, via their
     own external scp/rsync session -- entirely outside Django.
  3. Once confirmed pulled, the admin triggers "reclaim", which deletes
     what's in ARCHIVE_ROOT and stamps reclaimed_at.

The one thing that makes step 3 safe is that only one archive batch may be
outstanding at a time, across BOTH models: "archive" refuses outright if
anything -- an upload or a radio capture -- is still sitting
archived-and-unreclaimed anywhere. Without that, a second batch could land
in ARCHIVE_ROOT between the admin's pull and their reclaim click, and
"reclaim" would delete data that was never actually backed up.
"""
import shutil
from pathlib import Path

from django.conf import settings
from django.utils import timezone


class ArchiveBatchPending(Exception):
    """Raised by move_to_archive() when a previous batch -- an upload OR a
    radio capture -- is still sitting in ARCHIVE_ROOT, unreclaimed."""


def any_batch_pending():
    from radio.models import RadioCapture

    from .models import IngestedFile

    pending = {"archived_at__isnull": False, "reclaimed_at__isnull": True}
    return (
        IngestedFile.objects.filter(**pending).exists()
        or RadioCapture.objects.filter(**pending).exists()
    )


def move_to_archive(queryset, *, source_root, archive_subdir, path_field, eligible_statuses, status_field="status"):
    """
    Step A. Moves each eligible row's file from source_root into
    ARCHIVE_ROOT/archive_subdir (preserving the relative path), stamping
    archived_at. All-or-nothing: refuses entirely, before moving anything,
    if any previously-archived row (either model) hasn't been reclaimed
    yet. Returns (archived_count, missing_file_count).
    """
    if any_batch_pending():
        raise ArchiveBatchPending(
            f"A previous archive batch hasn't been reclaimed yet -- pull everything from "
            f"{settings.ARCHIVE_ROOT} and run the reclaim action/command first."
        )

    archive_root = Path(settings.ARCHIVE_ROOT) / archive_subdir
    eligible = queryset.filter(**{f"{status_field}__in": eligible_statuses}, archived_at__isnull=True)
    archived = missing = 0
    now = timezone.now()
    for obj in eligible.iterator():
        rel_path = getattr(obj, path_field)
        if rel_path:
            src = Path(source_root) / rel_path
            dst = archive_root / rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(src), str(dst))
            except FileNotFoundError:
                missing += 1
        obj.archived_at = now
        obj.save(update_fields=["archived_at"])
        archived += 1
    return archived, missing


def reclaim_from_archive(queryset, *, archive_subdir, path_field):
    """
    Step B. Deletes ARCHIVE_ROOT/archive_subdir/<path> for rows with
    archived_at set and reclaimed_at not set, then stamps reclaimed_at
    regardless (a missing file is tolerated, never retried). Operates on
    DB-tracked rows rather than wiping the directory wholesale -- the
    sequential-batch guarantee in move_to_archive() is what makes that
    equivalent in practice to "delete what's in the folder", while staying
    safe against any stray untracked file. Returns
    (deleted_count, missing_count, bytes_freed).
    """
    archive_root = Path(settings.ARCHIVE_ROOT) / archive_subdir
    candidates = queryset.filter(archived_at__isnull=False, reclaimed_at__isnull=True)
    deleted = missing = bytes_freed = 0
    now = timezone.now()
    for obj in candidates.iterator():
        rel_path = getattr(obj, path_field)
        size = None
        if rel_path:
            full_path = archive_root / rel_path
            try:
                size = full_path.stat().st_size
                full_path.unlink()
            except FileNotFoundError:
                pass
        if size is not None:
            deleted += 1
            bytes_freed += size
        else:
            missing += 1
        obj.reclaimed_at = now
        obj.save(update_fields=["reclaimed_at"])
    return deleted, missing, bytes_freed
