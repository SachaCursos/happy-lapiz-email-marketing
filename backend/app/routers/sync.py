from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlmodel import Session
from app.database import get_session
from app.core.deps import require_admin
from app.models.user import User
from app.services.sync_hotboat import sync_contacts
from app.services.tc_import import import_tc_csv

router = APIRouter()


@router.post("/run")
def run_sync(
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    """Sincroniza contactos de forma síncrona y devuelve el resultado."""
    try:
        result = sync_contacts(session)
        return {"status": "done", **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status")
def sync_status(_: User = Depends(require_admin)):
    return {"status": "idle"}


@router.post("/tc-import")
async def tc_import(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    """Importa formulario de Términos y Condiciones (CSV de Google Forms).
    Cruza la Marca temporal con all_appointments (±1 hora) para enriquecer cada contacto.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos CSV")
    try:
        content = await file.read()
        result = import_tc_csv(content, session)
        return {"status": "done", **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
