def get_user_projects(user_id=None, db_session=None, projects_dir=None):
    """
    獲取用戶的專案列表，支持從資料庫或目錄獲取

    :param user_id: 用戶ID
    :param db_session: 資料庫會話
    :param projects_dir: 專案目錄
    :return: 專案名稱列表
    """
    from database.db_manager import DatabaseManager
    from database.models import Project
    import os

    projects = []

    # 從資料庫獲取專案
    if user_id and db_session:
        projects = db_session.query(Project).filter_by(owner_id=user_id).all()
        return [project.name for project in projects]

    # 從目錄獲取專案 (向後兼容)
    elif projects_dir and os.path.exists(projects_dir):
        return [d for d in os.listdir(projects_dir)
                if os.path.isdir(os.path.join(projects_dir, d))]

    return projects