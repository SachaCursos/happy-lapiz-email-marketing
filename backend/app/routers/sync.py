from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlmodel import Session
from app.database import get_session
from app.core.deps import require_admin, get_current_shop
from app.models.user import User
from app.models.shop import Shop
from app.services.tc_import import import_tc_csv

router = APIRouter()


@router.get("/status")
def sync_status(_: User = Depends(require_admin)):
    return {"status": "idle"}


@router.post("/tc-import")
async def tc_import(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
    shop: Shop = Depends(get_current_shop),
):
    """Importa formulario de Términos y Condiciones (CSV de Google Forms)."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos CSV")
    try:
        content = await file.read()
        result = import_tc_csv(content, session, shop.id)
        return {"status": "done", **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
