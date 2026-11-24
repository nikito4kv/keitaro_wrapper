"""Таблицы приложения.

Сами кампании живут в Keitaro. Здесь хранится только то, чего в Keitaro нет:
выбранные по умолчанию домен, группа и источник, и журнал кампаний, созданных через это приложение.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CampaignDefaults(Base):
    """Домен, группа и источник, с которыми создаются кампании. В таблице одна строка с id = 1."""

    __tablename__ = "campaign_defaults"

    SINGLETON_ID = 1

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    domain_id: Mapped[int] = mapped_column(Integer)
    domain_name: Mapped[str] = mapped_column(String(255))
    domain_url: Mapped[str] = mapped_column(String(255))
    group_id: Mapped[int] = mapped_column(Integer)
    group_name: Mapped[str] = mapped_column(String(255))
    traffic_source_id: Mapped[int] = mapped_column(Integer)
    traffic_source_name: Mapped[str] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CreatedCampaign(Base):
    """Кампания, успешно созданная в Keitaro через это приложение."""

    __tablename__ = "created_campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    keitaro_campaign_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(255))
    alias: Mapped[str] = mapped_column(String(64))
    url: Mapped[str] = mapped_column(String(512))
    countries: Mapped[list[str]] = mapped_column(JSON)
    redirect_url: Mapped[str] = mapped_column(String(512))
    offer_id: Mapped[int] = mapped_column(Integer)
    offer_name: Mapped[str] = mapped_column(String(255))
    domain_name: Mapped[str] = mapped_column(String(255))
    group_name: Mapped[str] = mapped_column(String(255))
    traffic_source_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class StreamOffer(Base):
    """Оффер в потоке кампании, как его видит редактор.

    У строки две половины. «Черновик» (share, removed, pinned) показывает, чего хочет человек.
    «Как в Keitaro» (keitaro_share) показывает, что было в трекере при последней сверке.
    Пока половины расходятся, у потока есть неотправленные изменения.
    """

    __tablename__ = "stream_offers"
    __table_args__ = (UniqueConstraint("stream_id", "offer_id", name="uq_stream_offers_stream_offer"),)

    # Порядок строк по id и есть порядок офферов в потоке: от него зависит, кому достанется остаток доли.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(Integer, index=True)
    stream_id: Mapped[int] = mapped_column(Integer, index=True)
    offer_id: Mapped[int] = mapped_column(Integer)

    # Черновик
    share: Mapped[int] = mapped_column(Integer, default=0)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)

    # Как в Keitaro: доля при последней сверке, None означает «в потоке трекера этого оффера нет»
    keitaro_share: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    # Был ли оффер в Keitaro хоть раз. Если нет, при удалении строку незачем хранить.
    was_in_keitaro: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def unsent(self) -> bool:
        """Отличается ли черновик от того, что сейчас в Keitaro."""
        if self.removed:
            return self.keitaro_share is not None
        return self.keitaro_share is None or self.share != self.keitaro_share
