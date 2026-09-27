"""
Uchala xizmatni (backend API, Writing bot, Speaking bot) BITTA Render
xizmatida, alohida jarayon (subprocess) sifatida birga ishga tushiradi.

Nega subprocess (alohida jarayon) usuli tanlandi:
  - Har bir jarayon o'zining ALOHIDA Python muhitida ishlaydi (sys.modules
    keshi alohida), shuning uchun uchala loyihada ham bor bo'lgan bir xil
    nomli fayllar (masalan har birida o'z "evaluator.py", "config.py"
    fayli bor) BIR-BIRIGA HECH QANDAY TA'SIR QILMAYDI. Kodni qayta yozish
    yoki import yo'llarini o'zgartirish shart emas.
  - Agar bitta jarayon (masalan bitta bot) xatolik bilan yiqilsa,
    qolган ikkitasi ishlashda davom etadi.

Render faqat BITTA portni (`$PORT`) tashqi so'rovlar uchun tekshiradi —
shuning uchun faqat backend (FastAPI/uvicorn) shu portni band qiladi.
Botlarning o'z ichki "health-check" serverlari esa (agar bo'lsa) boshqa,
tashqi ko'rinmaydigan portlarga o'tkaziladi — bu ularning $PORT bilan
to'qnashib, xatolik berishining oldini oladi.
"""
import os
import subprocess
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = os.environ.get("PORT", "10000")


def spawn(name: str, folder: str, cmd: list, extra_env: dict | None = None) -> subprocess.Popen:
    """Berilgan papka ichida, berilgan buyruqni alohida jarayon sifatida
    ishga tushiradi. extra_env orqali shu jarayonga xos muhit
    o'zgaruvchilarini qo'shish/o'zgartirish mumkin (masalan PORT)."""
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    cwd = os.path.join(BASE_DIR, folder)
    print(f"[start.py] Ishga tushirilmoqda: {name} (papka: {folder})")
    return subprocess.Popen(cmd, cwd=cwd, env=env)


def main():
    processes = {}

    # 1) BACKEND — FastAPI/uvicorn. Bu jarayon $PORT ni band qiladi,
    #    chunki Render tashqi so'rovlarni aynan shu portga yo'naltiradi.
    processes["backend"] = spawn(
        "Backend (FastAPI)",
        "backend",
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", PORT],
    )

    # 2) WRITING BOT — polling rejimida ishga tushirish uchun,
    #    RENDER_EXTERNAL_URL / WEBHOOK_BASE_URL o'zgaruvchilarini shu
    #    jarayondan "yashiramiz" (aks holda u o'zining webhook serverini
    #    $PORT'da ishga tushirishga urinib, backend bilan to'qnashadi).
    writing_env = {"RENDER_EXTERNAL_URL": "", "WEBHOOK_BASE_URL": ""}
    processes["writing_bot"] = spawn(
        "Writing bot",
        "writing_bot",
        [sys.executable, "bot.py"],
        extra_env=writing_env,
    )

    # 3) SPEAKING BOT — ichki health-check serveri bor, uni $PORT bilan
    #    to'qnashmasligi uchun boshqa (tashqi ko'rinmaydigan) portga o'tkazamiz.
    speaking_env = {"PORT": "8081"}
    processes["speaking_bot"] = spawn(
        "Speaking bot",
        "speaking_bot",
        [sys.executable, "bot.py"],
        extra_env=speaking_env,
    )

    print("[start.py] Barcha 3 ta xizmat ishga tushirildi. Kuzatuv boshlandi...")

    # Barcha jarayonlarni doimiy kuzatib boramiz. Agar biror jarayon
    # to'xtab qolsa, uni avtomatik qayta ishga tushiramiz — shunda bitta
    # xizmatdagi vaqtinchalik xatolik butun loyihani to'xtatib qo'ymaydi.
    while True:
        time.sleep(15)
        for name, proc in list(processes.items()):
            if proc.poll() is not None:
                print(f"[start.py] OGOHLANTIRISH: {name} to'xtadi (kod: {proc.returncode}). Qayta ishga tushirilmoqda...")
                if name == "backend":
                    processes[name] = spawn("Backend (FastAPI)", "backend",
                                            [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", PORT])
                elif name == "writing_bot":
                    processes[name] = spawn("Writing bot", "writing_bot",
                                            [sys.executable, "bot.py"], extra_env=writing_env)
                elif name == "speaking_bot":
                    processes[name] = spawn("Speaking bot", "speaking_bot",
                                            [sys.executable, "bot.py"], extra_env=speaking_env)


if __name__ == "__main__":
    main()
