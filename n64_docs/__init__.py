"""
Shared Sphinx setup (theme, styling, C++ API generation)
"""
import datetime
import os
import subprocess

__version__ = "1.0.0"

_PKG_DIR = os.path.abspath(os.path.dirname(__file__))
STATIC_DIR = os.path.join(_PKG_DIR, "static")

ENV_FAST = "N64_DOCS_FAST"
ENV_SKIP_DOXYGEN = "N64_DOCS_SKIP_DOXYGEN"

_DOXYGEN_DEFAULTS = {
    "RECURSIVE": "YES",
    "FILE_PATTERNS": "*.h *.hpp",
    "GENERATE_HTML": "NO",
    "GENERATE_LATEX": "NO",
    "GENERATE_XML": "YES",
    "XML_OUTPUT": "xml",
    "XML_PROGRAMLISTING": "NO",
    "EXTRACT_ALL": "YES",
    "EXTRACT_PRIVATE": "NO",
    "EXTRACT_STATIC": "YES",
    "JAVADOC_AUTOBRIEF": "YES",
    "QT_AUTOBRIEF": "YES",
    "QUIET": "YES",
    "WARN_IF_UNDOCUMENTED": "NO",
    # @license renders as a small note; @TODO maps to the builtin @todo.
    "ALIASES": '"license=@par License:^^" "TODO=@todo"',
    # Expand macros so signatures parse cleanly
    "ENABLE_PREPROCESSING": "YES",
    "MACRO_EXPANSION": "YES",
    "EXPAND_ONLY_PREDEF": "NO",
}

_API_DEFAULTS = {
    "out_dir": "docs/manual/api",
    "title": "C++ API",
    "intro": "",
    "doxygen": {},
}


def is_fast():
    return os.environ.get(ENV_FAST) == "1"


def setup_project(ns, project, author, copyright=None, logo="logo.png",
                  favicon="favicon.ico", cpp_api=None):

    docs_dir = os.path.abspath(os.path.dirname(ns["__file__"]))
    fast = is_fast()

    ns["project"] = project
    ns["author"] = author
    ns["copyright"] = copyright or "{0}, {1}".format(datetime.date.today().year, author)

    ns["extensions"] = ["myst_parser", "n64_docs"]
    ns["templates_path"] = ["_templates"]
    ns["exclude_patterns"] = ["_build", "Thumbs.db", ".DS_Store", ".venv"]
    ns["suppress_warnings"] = []

    if cpp_api:
        api = dict(_API_DEFAULTS, **cpp_api)
        if isinstance(api["input"], str):
            api["input"] = [api["input"]]
        ns["n64_docs_cpp_api"] = api

        if fast:
            ns["exclude_patterns"].append(api["out_dir"])
            ns["suppress_warnings"] += ["toc", "ref"]
            print("[n64_docs] FAST mode: skipping C++ API (Doxygen/Breathe).")
        else:
            ns["extensions"].append("breathe")
            ns["suppress_warnings"].append("duplicate_declaration.cpp")
            ns["breathe_projects"] = {api["name"]: os.path.join(docs_dir, "_build", "doxygen", "xml")}
            ns["breathe_default_project"] = api["name"]
            ns["breathe_default_members"] = ("members",)
            ns["cpp_maximum_signature_line_length"] = 90
            ns["maximum_signature_line_length"] = 90

    ns["html_theme"] = "furo"
    # Project files come last so they can override the shared ones.
    ns["html_static_path"] = [STATIC_DIR, "_static"]
    if favicon and os.path.exists(os.path.join(docs_dir, "_static", favicon)):
        ns["html_favicon"] = "_static/" + favicon
    ns["html_css_files"] = ["custom.css"]

    ns["html_theme_options"] = {
        "sidebar_hide_name": bool(logo),
        "light_css_variables": {
            "font-stack": "Noto, Arial, sans-serif",
            # C++ API token colors
            "color-api-name": "#F5A937",       # symbol name (e.g. addObject)
            "color-api-pre-name": "#5a6b7b",   # namespace / class qualifier
            "color-api-keyword": "#a626a4",    # const, class, inline, template
            "color-api-paren": "#5a6b7b",      # parentheses
            "color-api-background": "#f0f2f4", # signature header background
        },
        "dark_css_variables": {
            "color-api-name": "#F5A937",
            "color-api-pre-name": "#9aa7b4",
            "color-api-keyword": "#d6a0ff",
            "color-api-paren": "#9aa7b4",
            "color-api-background": "#222225",
        },
    }
    if logo:
        ns["html_theme_options"]["light_logo"] = logo
        ns["html_theme_options"]["dark_logo"] = logo


def _doxygen_config(app, api, xml_root):
    opts = dict(_DOXYGEN_DEFAULTS)
    opts["PROJECT_NAME"] = '"{0}"'.format(app.config.project)
    opts["INPUT"] = " ".join('"{0}"'.format(p) for p in api["input"])
    opts["OUTPUT_DIRECTORY"] = '"{0}"'.format(xml_root)
    opts.update(api["doxygen"])
    return "".join("{0} = {1}\n".format(k, v) for k, v in opts.items())


def _generate_api(app):
    api = app.config.n64_docs_cpp_api
    if not api or is_fast():
        return

    xml_dir = app.config.breathe_projects[api["name"]]
    if os.environ.get(ENV_SKIP_DOXYGEN) == "1":
        print("[n64_docs] SKIP_DOXYGEN: reusing existing C++ API "
              "(no Doxygen/_apigen run).")
        return

    os.makedirs(xml_dir, exist_ok=True)
    try:
        subprocess.run(["doxygen", "-"], cwd=app.confdir, check=True,
                       input=_doxygen_config(app, api, os.path.dirname(xml_dir)), text=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as err:
        if not os.listdir(xml_dir):
            raise
        print("[n64_docs] WARNING: doxygen not run ({0}); using existing XML.".format(err))

    from . import _apigen
    _apigen.generate(
        xml_dir=xml_dir,
        out_dir=os.path.join(app.confdir, api["out_dir"]),
        project=api["name"],
        root_title=api["title"],
        intro=api["intro"],
    )


def setup(app):
    app.add_config_value("n64_docs_cpp_api", None, "env")
    # Runs before sources are collected, so the generated pages are picked up.
    app.connect("builder-inited", _generate_api)
    return {"version": __version__, "parallel_read_safe": True}
