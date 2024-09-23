"""
Global store for the application. Modulde created to store the dictionaries task -> sid and sid -> ifc_model.
"""


class GlobalStore:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GlobalStore, cls).__new__(cls)

            # Dictionary to map task -> sid
            cls._instance.task_to_sid = {}
            
            # Dictionary to map sid -> ifc_model
            cls._instance.sid_to_ifc_model = {}
        return cls._instance

# Singleton instance of GlobalStore
global_store = GlobalStore()