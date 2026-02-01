def register_blueprints(app):
    from app.routes.page_routes import bp as page_bp
    from app.routes.import_routes import bp as import_bp
    from app.routes.cluster_routes import bp as cluster_bp
    from app.routes.query_routes import bp as query_bp
    from app.routes.export_routes import bp as export_bp
    from app.routes.settings_routes import bp as settings_bp

    app.register_blueprint(page_bp)
    app.register_blueprint(import_bp)
    app.register_blueprint(cluster_bp)
    app.register_blueprint(query_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(settings_bp)
