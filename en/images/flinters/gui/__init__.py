"""Flint GUI public compatibility interface."""
import tkinter as tk
from tkinter import font as tkfont, ttk, filedialog, simpledialog, messagebox  # Legacy public imports
from .style import FlintTheme
from .menu import FlintMenuMixin
from .window import FlintWindowMixin
from .widget import FlintWidgetMixin
from .scroll import FlintScrollMixin

class FlintStyle(FlintMenuMixin, FlintWindowMixin, FlintWidgetMixin, FlintScrollMixin, FlintTheme):
    """Public Flint GUI style and helper API."""

from .state import FlintWindowState
from .selection import FlintSelection
from .namecolor import FlintNameColorEditor
from .filelist import FlintFileList
