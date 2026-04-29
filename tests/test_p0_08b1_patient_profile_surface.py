from __future__ import annotations
import asyncio
from dataclasses import dataclass
from pathlib import Path

import test_patient_existing_booking_shortcut_pat_a3_2 as existing
from app.application.clinic_reference import ClinicReferenceService, InMemoryClinicReferenceRepository
from app.common.i18n import I18nService
from app.domain.clinic_reference.models import Branch, Clinic
from app.interfaces.bots.patient.router import make_router
from app.interfaces.cards import CardCallbackCodec, CardRuntimeCoordinator, CardRuntimeStateStore
from app.interfaces.cards.runtime_state import InMemoryRedis

@dataclass(frozen=True)
class _Option:
    patient_id:str; display_name:str; relationship_type:str; phone:str|None=None

class _Selector:
    def __init__(self, mode="single"):
        self.mode=mode
    async def resolve_for_telegram(self, *, clinic_id:str, telegram_user_id:int):
        if self.mode=="none":
            return type("R",(),{"mode":"phone_required","options":(),"selected_patient_id":None})()
        if self.mode=="multiple":
            opts=(_Option("pat_1","Юрий","self","+1"),_Option("pat_2","Мария","child",None))
            return type("R",(),{"mode":"multiple_profiles","options":opts,"selected_patient_id":None})()
        opts=(_Option("pat_1","Юрий","self","+1"),)
        return type("R",(),{"mode":"single_match","options":opts,"selected_patient_id":"pat_1"})()

class _Profile:
    async def get_profile_details(self, *, clinic_id:str, patient_id:str):
        return type("P",(),{"email":"a@b.c","profile_completion_state":"partial"})()

class _Pref:
    async def get_preferences(self, *, patient_id:str):
        return type("Pref",(),{"preferred_language":"ru","default_branch_id":"branch_1","preferred_reminder_channel":"telegram"})()


def _ref():
    repo=InMemoryClinicReferenceRepository(); repo.upsert_clinic(Clinic(clinic_id="clinic_main",code="MAIN",display_name="Main",timezone="UTC",default_locale="ru")); repo.upsert_branch(Branch(branch_id="branch_1",clinic_id="clinic_main",display_name="Филиал 1",address_text="-",timezone="UTC")); return ClinicReferenceService(repo)

def _build(selector=None, profile=None, pref=None):
    i18n=I18nService(locales_path=Path("locales"), default_locale="ru")
    runtime=CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    router=make_router(i18n=i18n,booking_flow=existing._BookingFlowStub(),reference=_ref(),reminder_actions=existing._ReminderActions(),recommendation_service=None,care_commerce_service=None,patient_profile_service=profile,patient_preference_service=pref,booking_patient_selector_service=selector,recommendation_repository=existing._RepoUnique(),default_locale="ru",card_runtime=runtime,card_callback_codec=CardCallbackCodec(runtime=runtime))
    return router

def _handler(router,name,kind='callback'):
    for h in router.callback_query.handlers if kind=='callback' else router.message.handlers:
        if h.callback.__name__==name: return h.callback
    raise AssertionError(name)

def _btns(markup): return {b.text:b.callback_data for r in markup.inline_keyboard for b in r}
def _latest(cb):
    if cb.bot.edits:
        item=cb.bot.edits[-1]
        return item["text"], item.get("reply_markup")
    if cb.message.answers:
        return cb.message.answers[-1]
    if cb.answers:
        return cb.answers[-1], None
    return cb.message.answers[-1]

def test_home_has_profile_button():
    router=_build()
    m=existing._Message('/start'); asyncio.run(_handler(router,'start',kind='message')(m))
    _,mk=m.answers[-1]; btns=_btns(mk)
    assert '👤 Профиль' in btns and btns['👤 Профиль']=='phome:profile'
    assert '🦷 Записаться на приём' in btns and '📅 Моя запись' in btns

def test_profile_unavailable_and_not_found_and_single_and_multiple_and_validation():
    router=_build()
    cb=existing._Callback('phome:profile',user_id=1001); asyncio.run(_handler(router,'patient_home_profile')(cb)); assert 'Профиль пока недоступен' in _latest(cb)[0]
    router=_build(selector=_Selector('none'),profile=_Profile(),pref=_Pref())
    cb=existing._Callback('phome:profile',user_id=1001); asyncio.run(_handler(router,'patient_home_profile')(cb)); text,mk=_latest(cb); assert 'Профиль не найден' in text; assert {'📅 Моя запись','🦷 Записаться на приём','🏠 Главное меню'}<=set(_btns(mk))
    router=_build(selector=_Selector('single'),profile=_Profile(),pref=_Pref())
    cb=existing._Callback('phome:profile',user_id=1001); asyncio.run(_handler(router,'patient_home_profile')(cb)); text,mk=_latest(cb); assert 'Профиль пациента' in text and 'Юрий' in text and 'None' not in text and 'patient_id' not in text; assert '✏️' not in ''.join(_btns(mk))
    router=_build(selector=_Selector('multiple'),profile=_Profile(),pref=_Pref())
    cb=existing._Callback('phome:profile',user_id=1001); asyncio.run(_handler(router,'patient_home_profile')(cb)); text,mk=_latest(cb); btns=_btns(mk); assert 'Кого настраиваем' in text; assert any(v=='profile:open:pat_1' for v in btns.values()) and all('pat_' not in k for k in btns)
    bad=existing._Callback('profile:open:pat_X',user_id=1001); asyncio.run(_handler(router,'patient_profile_open')(bad)); assert 'Профиль не найден' in _latest(bad)[0]
