import ast
import os


def check_file_for_db_usage(filepath: str):
    """
    Statically analyzes a file to ensure it does not use SQLAlchemy queries
    like 'db.query', 'db.session', 'db.add', etc.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr in ("query", "session", "add", "commit"):
                # Make sure it's not a generic attribute that just happens to be named this.
                # Specifically we want to avoid `db.session()` or `db.query()` where `db` is from SQLAlchemy.
                # As a strict boundary check, we'll just ensure these words aren't used as attributes 
                # in the services/facades directly connected to 'db' or 'session'.
                if isinstance(node.value, ast.Name) and node.value.id in ("db", "self.db", "session"):
                    raise AssertionError(f"Found direct database operation '{node.attr}' in {filepath}")


def test_services_have_no_db_queries():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    
    patient_svc = os.path.join(base_dir, "services", "patient_service.py")
    session_svc = os.path.join(base_dir, "services", "session_service.py")
    
    check_file_for_db_usage(patient_svc)
    check_file_for_db_usage(session_svc)


def test_digital_thread_has_no_db_queries():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    thread_file = os.path.join(base_dir, "digital_thread", "thread.py")
    
    check_file_for_db_usage(thread_file)
