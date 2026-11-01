"""Start: streamlit run app.py"""
exec(compile((__import__("pathlib").Path(__file__).parent / "leis_ui.py").read_text(encoding="utf-8"), "leis_ui.py", "exec"))
