# test_project_structure.py
import importlib
import os

def test_project_structure():
    """Verify the project structure was correctly set up."""
    # Test main package can be imported
    import ktrdr
    print(f"KTRDR version: {ktrdr.__version__}")
    
    # Test all submodules can be imported
    modules = ['data', 'indicators', 'fuzzy', 'neural', 'visualization', 'ui']
    for module in modules:
        full_name = f'ktrdr.{module}'
        imported = importlib.import_module(full_name)
        print(f"Successfully imported {full_name}")
    
    # Check directory structure
    for module in modules:
        assert os.path.isdir(f'ktrdr/{module}'), f"Directory ktrdr/{module} not found"
        assert os.path.isfile(f'ktrdr/{module}/__init__.py'), f"__init__.py not found in ktrdr/{module}"
    
    print("Project structure verification complete!")

if __name__ == "__main__":
    test_project_structure()