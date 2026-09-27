# -*- coding: utf-8 -*-
"""
Multilevel CEFR Writing — vazifalar tavsifi va baholash mezonlari.
Manba: "Writing Ko'p darajali baholash me'zoni (yangi format)" hujjati.
(Foydalanuvchining ishlab turgan Writing botidan olingan, o'zgarishsiz.)
"""

LANGUAGE_FUNCTIONS = """
- Fikr bildirish
- Sabablar va asoslar keltirish
- Umid va rejalarni tasvirlash
- Aniq ma'lumot berish
- Mavhum g'oyalarni ifodalash
- Ishonch, ehtimollik, shubhani ifodalash
- Umumlashtirish va aniqlik kiritish
- Birlashtirish va baholash
- Taxmin qilish va faraz bildirish
- Fikrni ehtiyotkorlik bilan bildirish
- Fikrning turli darajalarini ifodalash
- Rozilik / norozilik bildirish
- Reaksiya bildirish (masalan, befarqlik)
- Bahsni izchil rivojlantirish
- Qisman rozi bo'lish (murosaga kelish)
- Muayyan fikr, hissiyot yoki masalaga urg'u berish
- Fikrni ishonarli tarzda himoya qilish
- Shikoyat qilish, taklif bildirish
"""

TASKS = {
    "1.1": {
        "title": "Writing Task 1.1 — Norasmiy email (do'stga)",
        "target_level": "B1",
        "word_range": "≈50 so'z",
        "max_score": 5,
        "rubric": """
Vazifa: Nomzod topshiriqdagi qisqa xat/e'longa tayangan holda DO'STIGA yozilgan
norasmiy elektron xat yozadi (o'z his-tuyg'ulari va rejalari haqida).
Tavsiya etilgan hajm: ~50 so'z.
Kutilayotgan daraja: B1.
Kerakli leksik daraja: K1-K3. Kerakli grammatik daraja: B1 grammatik vositalar,
paragraf darajasida yozish, fikrlar orasida yetarli bog'lanish (cohesion).

BAHOLASH SHKALASI (0-5, 6 pog'onali, holistik):
0 — Javob yo'q yoki vazifaga umuman mos emas / baholab bo'lmaydigan daraja (A1 dan past
    yoki mutlaqo bog'liq bo'lmagan matn).
1 — A1 darajasi: juda oddiy, uzuq-yuluq iboralar, vazifa deyarli bajarilmagan,
    tez-tez tushunishga xalaqit beruvchi xatolar.
2 — A2 darajasi: sodda gaplar, cheklangan bog'lovchilar, vazifa qisman bajarilgan,
    xatolar ko'p lekin asosiy fikr tushunarli.
3 — B1 darajasiga yaqinlashgan, lekin barqaror emas: vazifa asosan bajarilgan,
    ba'zi B1 grammatik vositalari va bog'lovchilar bor, lekin izchillik va aniqlikda
    bir tekis emas.
4 — B1 darajasi ishonchli namoyon bo'lgan: vazifa to'liq bajarilgan, norasmiy uslub
    izchil saqlangan, paragraf darajasida yozilgan, fikrlar orasida yetarli bog'lanish,
    B1 grammatikasi asosan to'g'ri qo'llangan.
5 — B1 darajasidan yuqori (B2 ga yaqin/B2): boy va aniq til vositalari, tabiiy
    norasmiy uslub, yuqori izchillik va bog'lanish, xatolar deyarli yo'q yoki
    kommunikatsiyaga ta'sir qilmaydi.

KO'ZDA TUTILGAN TIL FUNKSIYALARI (matnda qay darajada namoyon bo'lganini ham
baholang, bular yuqori ball uchun muhim ko'rsatkich):
{lang_functions}
""".format(lang_functions=LANGUAGE_FUNCTIONS),
    },
    "1.2": {
        "title": "Writing Task 1.2 — Rasmiy email (menejerga/notanish shaxsga)",
        "target_level": "B2",
        "word_range": "≈120-150 so'z",
        "max_score": 5,
        "rubric": """
Vazifa: Xuddi shu topshiriqdagi ma'lumotga tayangan holda NOTANISH/RASMIY shaxsga
(rahbariyat, mijozlar xizmati va h.k.) rasmiy elektron xat yozadi.
Tavsiya etilgan hajm: 120-150 so'z.
Kutilayotgan daraja: B2.
Kerakli leksik daraja: K4-K5. Kerakli grammatik daraja: B2 grammatikasi, bog'lovchi
vositalar (cohesion) va izchillik (coherence) yaxshi namoyon bo'lishi kerak.

BAHOLASH SHKALASI (0-5, 6 pog'onali, holistik):
0 — Javob yo'q yoki vazifaga mos emas.
1 — A2 va undan past: rasmiy uslub deyarli yo'q, vazifa bajarilmagan, ko'p xatolar.
2 — B1 dan past: rasmiy uslubga urinish bor, lekin barqaror emas, vazifa qisman
    bajarilgan, cheklangan leksika/grammatika.
3 — B1-B2 orasida beqaror: vazifa asosan bajarilgan (3 ta harakat bandiga javob
    berilgan), lekin rasmiy registr, izchillik yoki grammatikada nomuvofiqliklar bor.
4 — B2 darajasi ishonchli namoyon bo'lgan: vazifa to'liq bajarilgan (barcha 3 ta
    harakat bandiga javob berilgan), rasmiy uslub izchil saqlangan, yaxshi
    tuzilgan paragraflar, B2 grammatikasi va bog'lovchi vositalar to'g'ri
    qo'llangan, K4-K5 leksika ishlatilgan.
5 — B2 darajasidan yuqori (C1 ga yaqin): murakkab tuzilmalar, yuqori aniqlikdagi
    rasmiy registr, teran izchillik, xatolar deyarli yo'q.

KO'ZDA TUTILGAN TIL FUNKSIYALARI (matnda qay darajada namoyon bo'lganini ham
baholang, bular yuqori ball uchun muhim ko'rsatkich):
{lang_functions}
""".format(lang_functions=LANGUAGE_FUNCTIONS),
    },
    "2": {
        "title": "Writing Task 2 — Blog/forum posti yoki jurnal maqolasi",
        "target_level": "C1",
        "word_range": "180-200 so'z",
        "max_score": 6,
        "rubric": """
Vazifa: Nomzod umumiy qiziqish uyg'otuvchi mavzu doirasida onlayn nashr uchun
ijodiy-tavsifiy matn yozadi (blog posti / muhokama forumi posti / jurnal maqolasi).
O'z fikrini bayon qilib, g'oyalarini misollar bilan asoslashi kerak.
Tavsiya etilgan hajm: 180-200 so'z.
Kutilayotgan daraja: C1.
Kerakli grammatik daraja: C1 grammatikasi puxta egallanganligi, o'zaro bog'liqlik
(cohesion) va izchillik (coherence) yuqori darajada namoyon bo'lishi kerak.

BAHOLASH SHKALASI (0-6, 7 pog'onali, holistik):
0 — Javob yo'q yoki vazifaga mos emas.
1 — A2 va undan past.
2 — B1 darajasi: sodda tuzilma, cheklangan argumentatsiya, mavzu yuzaki yoritilgan.
3 — B1-B2 orasida: vazifa qisman bajarilgan, ba'zi misollar bor, lekin fikrlar
    yetarlicha rivojlantirilmagan yoki bog'lanish zaif.
4 — B2 darajasi: vazifa asosan bajarilgan, fikrlar misollar bilan asoslangan,
    lekin C1 uchun zarur bo'lgan til boyligi, mavhum fikr ifodasi yoki nozik
    argumentatsiya yetishmaydi.
5 — C1 darajasi ishonchli namoyon bo'lgan: mavzu chuqur va izchil yoritilgan,
    fikrlar aniq misollar bilan asoslangan, mavhum g'oyalar, ishonch/ehtimollik
    nozik ifodalangan, janrga mos ohang (blog/forum/maqola), yuqori cohesion va
    coherence, C1 grammatikasi va boy leksika ishonchli qo'llangan.
6 — C1 darajasidan yuqori (C2 ga yaqin): nozik, ishonarli, professional darajadagi
    yozuv, murakkab fikrlarni ravon va aniq ifodalash, deyarli xatosiz.

KO'ZDA TUTILGAN TIL FUNKSIYALARI (matnda qay darajada namoyon bo'lganini ham
baholang, bular yuqori ball uchun muhim ko'rsatkich, ayniqsa mavhum
g'oyalarni ifodalash, ishonch/ehtimollik bildirish va bahsni izchil
rivojlantirish C1 uchun kalit belgilardir):
{lang_functions}
""".format(lang_functions=LANGUAGE_FUNCTIONS),
    },
}

STANDARD_SCORE_TABLE = {
    16: 75, 15.5: 72, 15: 69, 14.5: 67, 14: 65, 13.5: 64, 13: 63,
    12.5: 62, 12: 61, 11.5: 59, 11: 57, 10.5: 55, 10: 53, 9.5: 51,
    9: 50, 8.5: 48, 8: 47, 7.5: 45, 7: 43, 6.5: 41, 6: 40, 5.5: 38,
    5: 37, 4.5: 35, 4: 33, 3.5: 31, 3: 28, 2.5: 25, 2: 21, 1.5: 17,
    1: 14, 0.5: 10, 0: 0,
}


def get_standard_score(raw_sum: float) -> int:
    keys = sorted(STANDARD_SCORE_TABLE.keys(), reverse=True)
    for k in keys:
        if raw_sum >= k:
            return STANDARD_SCORE_TABLE[k]
    return 0
