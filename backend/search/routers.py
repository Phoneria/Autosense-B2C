class ReferenceRouter:
    """Keep the copied analysis schema separate from B2C accounts/sessions."""

    def db_for_read(self, model, **hints):
        return "reference" if model._meta.app_label == "search" else "default"

    def db_for_write(self, model, **hints):
        if model._meta.app_label == "search":
            raise PermissionError("Analiz referans verileri salt okunurdur.")
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        return (obj1._meta.app_label == "search") == (obj2._meta.app_label == "search")

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db == "default" and app_label != "search"
