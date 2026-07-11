from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_plugin_manager
from app.api.schemas import PluginOut
from app.plugins.manager import PluginManager

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


@router.get("", response_model=list[PluginOut])
def list_plugins(manager: PluginManager = Depends(get_plugin_manager), _=Depends(get_current_user)):
    return [
        PluginOut(plugin_id=p.plugin_id, display_name=p.display_name, version=p.version)
        for p in manager.list_plugins()
    ]
