from sqlalchemy.orm import Session
from app.repositories.dashboard_repository import DashboardRepository

class DashboardService:

    @staticmethod
    def get_summary(db: Session, user_id: int):

        summary_data = DashboardRepository.get_dashboard_data(db, user_id)

        return summary_data



        





        