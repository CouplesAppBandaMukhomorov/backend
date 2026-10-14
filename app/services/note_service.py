import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.errors import BadRequest, NotFound
from app.models.couple import Couple
from app.models.note import Note
from app.models.user import User
from app.schemas.note import NoteCreate, NoteUpdate

NOTE_NOT_FOUND = "Note not found"


async def list_notes(
    db: AsyncSession,
    couple_id: uuid.UUID,
    limit: int,
    offset: int,
) -> list[Note]:
    stmt = (
        select(Note)
        .where(Note.couple_id == couple_id)
        .order_by(Note.pinned.desc(), Note.updated_at.desc(), Note.id.desc())
        .limit(limit)
        .offset(offset)
        .options(joinedload(Note.created_by), joinedload(Note.updated_by))
    )
    return list((await db.execute(stmt)).scalars().all())


async def load_note(db: AsyncSession, couple_id: uuid.UUID, note_id: uuid.UUID) -> Note:
    stmt = (
        select(Note)
        .where(Note.id == note_id, Note.couple_id == couple_id)
        .options(joinedload(Note.created_by), joinedload(Note.updated_by))
        .execution_options(populate_existing=True)
    )
    note = (await db.execute(stmt)).scalar_one_or_none()
    if note is None:
        raise NotFound(NOTE_NOT_FOUND, code="note_not_found")
    return note


async def create_note(
    db: AsyncSession,
    couple: Couple,
    user: User,
    payload: NoteCreate,
) -> Note:
    note = Note(
        couple_id=couple.id,
        title=payload.title,
        content=payload.content,
        pinned=payload.pinned,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db.add(note)
    await db.commit()
    return await load_note(db, couple.id, note.id)


async def update_note(
    db: AsyncSession,
    couple_id: uuid.UUID,
    note_id: uuid.UUID,
    user: User,
    payload: NoteUpdate,
) -> Note:
    note = await load_note(db, couple_id, note_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise BadRequest("Nothing to update", code="empty_update")
    for field, value in changes.items():
        setattr(note, field, value)
    note.updated_by_user_id = user.id
    await db.commit()
    return await load_note(db, couple_id, note_id)


async def delete_note(db: AsyncSession, couple_id: uuid.UUID, note_id: uuid.UUID) -> None:
    note = await load_note(db, couple_id, note_id)
    await db.delete(note)
    await db.commit()


async def delete_couple_notes(db: AsyncSession, couple_id: uuid.UUID) -> None:
    await db.execute(delete(Note).where(Note.couple_id == couple_id))
