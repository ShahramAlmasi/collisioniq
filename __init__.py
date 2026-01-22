def classFactory(iface):
    from .plugin import CollisionAnalyticsPlugin
    return CollisionAnalyticsPlugin(iface)
