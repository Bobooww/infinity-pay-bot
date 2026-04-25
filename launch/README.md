# 🚀 Infinity Pay — Launch Pack

> Всё что нужно чтобы запустить @InfinityPaySupportBot для 152 мерчантов.
> Открывай по порядку — сверху самое важное.

---

## 📚 Документы в этой папке

| Файл | Для кого | Когда читать |
|---|---|---|
| **[LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md)** | Shams | **Прямо сейчас.** Полный список что осталось сделать с владельцами и сроками |
| [TEAM_QUICKSTART.md](TEAM_QUICKSTART.md) | Daler, Laziza, support1, support2 | После того как они получили email + пароль |
| [AGENT_FIELD_KIT.md](AGENT_FIELD_KIT.md) | Andrew, Nick, A U, Behruz | Перед первым cold call / визитом к мерчанту |
| [BUSINESS_CARD.html](BUSINESS_CARD.html) + [BUSINESS_CARD.pdf](BUSINESS_CARD.pdf) | Andrew, Nick (потом другие агенты) | PDF готов — отправь в типографию (VistaPrint/Moo, $30-40 за 250 шт) |
| [MERCHANT_BROADCAST.md](MERCHANT_BROADCAST.md) | Daler (он рассылает) | Перед массовой рассылкой 152 мерчантам |
| [E2E_TEST_PLAN.md](E2E_TEST_PLAN.md) | Shams | Перед каждой массовой рассылкой / после деплоя |

---

## 🎯 Быстрый план запуска (TL;DR)

1. **Сегодня — инфраструктура** (`LAUNCH_CHECKLIST.md` секция A+B)
   - Раздать пароли команде, включить 2FA
   - DNS CNAME для `support.infinitypay.us`
   - Resend API key для писем
   - Sandbox Clover пока ждём prod

2. **Завтра — тестирование** (`E2E_TEST_PLAN.md`)
   - 15 тестов end-to-end
   - Удалить тестовые данные

3. **Через 2 дня — мерчанты** (`MERCHANT_BROADCAST.md`)
   - Daler шлёт первой волне 30 мерчантов
   - Мониторинг 24 часа
   - Если ок — остальные 122

4. **Параллельно — агенты в поле** (`AGENT_FIELD_KIT.md`, `BUSINESS_CARD.html`)
   - Печать визиток
   - 30-минутный созвон с каждым агентом
   - Andrew/Nick начинают cold calls

5. **Когда придёт Clover prod** (через 2-4 недели)
   - Меняешь `CLOVER_ENV=production`
   - Первый реальный мерчант через OAuth

---

## 🔗 Ссылки

| Что | Где |
|---|---|
| Дашборд (прод) | https://infinity-pay-dashboard-production.up.railway.app |
| Бот | https://t.me/InfinityPaySupportBot |
| GitHub бот | https://github.com/Bobooww/infinity-pay-bot |
| GitHub дашборд | https://github.com/Bobooww/infinity-pay-dashboard |
| Railway проект (дашборд) | https://railway.com/project/8d6e1a3d-9c1f-494c-acfa-e7958462ef7b |
| Будущий домен | https://support.infinitypay.us |

---

## 🆘 Если что-то непонятно

Открой `LAUNCH_CHECKLIST.md` — там пошагово что делать. Если конкретный пункт неясен — пиши Claude, помогу.

**Удачи! 💙**
