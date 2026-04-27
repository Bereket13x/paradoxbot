# =============================================================================
#  PARADOX Userbot Plugin - AI Setup Manager
#
#  Plugin Name:    ai_setup
#  Central hub for all PARADOX AI API keys and provider settings.
# =============================================================================

import os
import json
import asyncio
from pathlib import Path
from datetime import datetime
from telethon import events
from utils.utils import CipherElite
from utils.decorators import rishabh
from plugins.bot import add_handler

# ── Config file location ───────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR   = PROJECT_ROOT / "DB"
CONFIG_DIR.mkdir(exist_ok=True)
AI_CONFIG_FILE = CONFIG_DIR / "ai_config.json"


# ══════════════════════════════════════════════════════════════════════════
#  AIConfigManager
# ══════════════════════════════════════════════════════════════════════════

class AIConfigManager:
    """Centralized manager for all AI API keys and settings."""

    def __init__(self):
        self.config = {
            "gemini_api_key":  None,
            "nvidia_api_key":  None,
            "active_provider": "nvidia",   # default → NVIDIA
            "ai_enabled":      False,
            "last_updated":    None,
        }
        self._load()

    # ── Persistence ────────────────────────────────────────────────────────

    def _load(self):
        """Load config from disk, then fall back to environment variables."""
        try:
            if AI_CONFIG_FILE.exists():
                with open(AI_CONFIG_FILE, "r") as f:
                    self.config.update(json.load(f))
        except Exception as e:
            print(f"⚠️ AI Config load error: {e}")

        # Env-var fallbacks (don't overwrite if already on disk)
        if not self.config["gemini_api_key"]:
            val = os.environ.get("GEMINI_API_KEY")
            if val:
                self.config["gemini_api_key"] = val

        if not self.config["nvidia_api_key"]:
            val = os.environ.get("NVIDIA_API_KEY")
            if val:
                self.config["nvidia_api_key"] = val

        env_provider = os.environ.get("ACTIVE_PROVIDER", "").lower()
        if env_provider in ("nvidia", "gemini") and not AI_CONFIG_FILE.exists():
            self.config["active_provider"] = env_provider

        self._update_enabled()
        self._save()

    def _save(self):
        try:
            with open(AI_CONFIG_FILE, "w") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"⚠️ AI Config save error: {e}")

    def _update_enabled(self):
        """Set ai_enabled based on whether the active provider has a key."""
        self.config["ai_enabled"] = bool(self.get_active_key())

    # ── Setters ────────────────────────────────────────────────────────────

    def set_gemini_key(self, key: str | None):
        self.config["gemini_api_key"] = key.strip() if key else None
        self.config["last_updated"] = datetime.now().isoformat()
        os.environ["GEMINI_API_KEY"] = key.strip() if key else ""
        self._update_enabled()
        self._save()

    def set_nvidia_key(self, key: str | None):
        self.config["nvidia_api_key"] = key.strip() if key else None
        self.config["last_updated"] = datetime.now().isoformat()
        os.environ["NVIDIA_API_KEY"] = key.strip() if key else ""
        self._update_enabled()
        self._save()

    def set_provider(self, provider: str):
        if provider.lower() in ("nvidia", "gemini"):
            self.config["active_provider"] = provider.lower()
            os.environ["ACTIVE_PROVIDER"] = provider.lower()
            self._update_enabled()
            self._save()

    def clear_all(self):
        """Remove all stored API keys."""
        self.config["gemini_api_key"] = None
        self.config["nvidia_api_key"] = None
        self.config["ai_enabled"]     = False
        self.config["last_updated"]   = datetime.now().isoformat()
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("NVIDIA_API_KEY", None)
        self._save()

    # ── Getters ────────────────────────────────────────────────────────────

    def get_gemini_key(self) -> str | None:
        return self.config.get("gemini_api_key")

    def get_nvidia_key(self) -> str | None:
        return self.config.get("nvidia_api_key")

    def get_provider(self) -> str:
        return self.config.get("active_provider", "nvidia")

    def get_active_key(self) -> str | None:
        """Return the key for whichever provider is currently active."""
        if self.get_provider() == "gemini":
            return self.get_gemini_key()
        return self.get_nvidia_key()

    # Legacy alias — keeps pmpermit / Cipher_ai imports working
    def get_api_key(self) -> str | None:
        return self.get_gemini_key()

    def is_enabled(self) -> bool:
        return bool(self.get_active_key())


# ── Global instance (imported by paradox_ai, pmpermit, etc.) ──────────────
ai_config = AIConfigManager()


# ══════════════════════════════════════════════════════════════════════════
#  Plugin init — registers commands + handlers inside the function scope
# ══════════════════════════════════════════════════════════════════════════

def init(client):
    commands = [
        ".setai <key>   — Set Google Gemini API key",
        ".setnai <key>  — Set NVIDIA API key",
        ".rmai          — Remove ALL AI keys",
        ".aistatus      — Show AI configuration status",
    ]
    add_handler("ai_setup", commands, "🤖 AI Configuration Manager — Central hub for PARADOX AI keys")

    # ── .setai — set Gemini key ────────────────────────────────────────────

    @CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.setai(?:\s+(.+))?$"))
    @rishabh()
    async def _setai(event):
        key = event.pattern_match.group(1)
        if not key:
            await event.reply(
                "❌ **Usage:** `.setai <your_gemini_api_key>`\n\n"
                "📋 Get your key: https://aistudio.google.com/"
            )
            return

        ai_config.set_gemini_key(key.strip())
        msg = await event.reply(
            "✅ **Gemini API Key saved!**\n\n"
            "🤖 PARADOX AI is now **ACTIVE** for Gemini.\n"
            "⚡ Use `.paimode gemini` to switch to it.\n"
            "🔑 Use `.setnai <key>` to also set an NVIDIA key."
        )
        await asyncio.sleep(5)
        try:
            await msg.delete()
        except Exception:
            pass

    # ── .setnai — set NVIDIA key ───────────────────────────────────────────

    @CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.setnai(?:\s+(.+))?$"))
    @rishabh()
    async def _setnai(event):
        key = event.pattern_match.group(1)
        if not key:
            await event.reply(
                "❌ **Usage:** `.setnai <your_nvidia_api_key>`\n\n"
                "📋 Get your key: https://build.nvidia.com/"
            )
            return

        ai_config.set_nvidia_key(key.strip())
        msg = await event.reply(
            "✅ **NVIDIA API Key saved!**\n\n"
            "🤖 PARADOX AI is now **ACTIVE** for NVIDIA.\n"
            f"⚡ Model: mistralai/mistral-nemotron\n"
            "🔑 Use `.paimode nvidia` to switch to it."
        )
        await asyncio.sleep(5)
        try:
            await msg.delete()
        except Exception:
            pass

    # ── .rmai — clear all keys ─────────────────────────────────────────────

    @CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.rmai$"))
    @rishabh()
    async def _rmai(event):
        ai_config.clear_all()
        msg = await event.reply(
            "🛑 **All AI Keys removed!**\n\n"
            "AI features disabled across all PARADOX plugins."
        )
        await asyncio.sleep(5)
        try:
            await msg.delete()
        except Exception:
            pass

    # ── .aistatus — show config ────────────────────────────────────────────

    @CipherElite.on(events.NewMessage(outgoing=True, pattern=r"\.aistatus$"))
    @rishabh()
    async def _aistatus(event):
        gemini_key  = ai_config.get_gemini_key()
        nvidia_key  = ai_config.get_nvidia_key()
        provider    = ai_config.get_provider()

        gemini_disp = f"`✅ {gemini_key[:8]}...{gemini_key[-4:]}`" if gemini_key else "`❌ Not Set`"
        nvidia_disp = f"`✅ {nvidia_key[:8]}...{nvidia_key[-4:]}`" if nvidia_key else "`❌ Not Set`"

        await event.reply(
            f"📊 **PARADOX AI Configuration:**\n\n"
            f"⚡ **Active Provider:** `{provider.upper()}`\n"
            f"🟢 **AI Ready:** `{'Yes' if ai_config.is_enabled() else 'No'}`\n\n"
            f"🔑 **Gemini Key:** {gemini_disp}\n"
            f"🔑 **NVIDIA Key:** {nvidia_disp}\n\n"
            f"📝 **Commands:**\n"
            f"• `.setai <key>` — Set Gemini key\n"
            f"• `.setnai <key>` — Set NVIDIA key\n"
            f"• `.paimode nvidia/gemini` — Switch provider\n"
            f"• `.rmai` — Remove all keys\n\n"
            f"🔗 Gemini: https://aistudio.google.com/\n"
            f"🔗 NVIDIA: https://build.nvidia.com/"
        )

    print("✅ AI Setup Plugin initialized")
    return ai_config
