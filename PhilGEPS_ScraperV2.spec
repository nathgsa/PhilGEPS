# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['scraper_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\OPTIMA\\AppData\\Local\\Python\\pythoncore-3.14-64\\Lib\\site-packages\\customtkinter', 'customtkinter'), ('C:\\Users\\OPTIMA\\AppData\\Local\\Python\\pythoncore-3.14-64\\Lib\\site-packages\\playwright\\driver', 'playwright/driver'), ('C:\\Users\\OPTIMA\\AppData\\Local\\ms-playwright', 'playwright/driver/package/.local-browsers'), ('categories_config.json', '.'), ('general_merchandise_config.json', '.'), ('gui_config.json', '.'), ('README.md', '.'), ('requirements.txt', '.'), ('requirements_gui.txt', '.')],
    hiddenimports=['final_working_scraper', 'multi_category_scraper', 'data_cleaner', 'test_philgeps_connection', 'playwright', 'playwright.sync_api', 'playwright._impl._api_types', 'playwright._impl._browser', 'playwright._impl._browser_context', 'playwright._impl._page', 'playwright._impl._element_handle', 'playwright._impl._locator', 'playwright._impl._network', 'bs4', 'bs4.builder', 'bs4.builder._html5lib', 'bs4.builder._htmlparser', 'bs4.builder._lxml', 'pandas', 'pandas._libs', 'pandas._libs.tslibs', 'pandas.io.formats.style', 'numpy', 'numpy.core._multiarray_umath', 'requests', 'requests.adapters', 'urllib3', 'certifi', 'charset_normalizer', 'customtkinter', 'customtkinter.windows', 'customtkinter.windows.widgets', 'customtkinter.windows.widgets.core_rendering', 'darkdetect', 'tkinter', 'tkinter.ttk', 'tkinter.messagebox', 'tkinter.filedialog', 'threading', 'queue', 'json', 'csv', 're', 'math', 'subprocess', 'shutil', 'logging', 'argparse', 'typing', 'pathlib', 'datetime', 'io', 'socket', 'concurrent.futures'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'IPython', 'notebook', 'pytest'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PhilGEPS_ScraperV2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PhilGEPS_ScraperV2',
)
