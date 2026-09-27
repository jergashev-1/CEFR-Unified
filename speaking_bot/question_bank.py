"""
CEFR Multilevel Speaking imtihoni uchun namunaviy savollar banki.
Bu savollar rasmiy imtihon uslubiga mos ravishda tayyorlangan (har bir
Part uchun mos qiyinlik darajasida), lekin rasmiy imtihon savollarining
o'zi emas — mashq qilish uchun namunaviy savollardir.
"""
import random

QUESTION_BANK = {
    "1.1": [
        "What is your name and where are you from?",
        "What do you usually do at the weekend?",
        "Do you like your job or studies? Why or why not?",
        "What is your favourite food?",
        "How many people are there in your family?",
        "What time do you usually wake up?",
        "Do you prefer tea or coffee?",
        "What is the weather like today in your city?",
    ],
    "1.2": [
        "Tell me about a place you visited recently.",
        "What did you do last weekend?",
        "Describe your daily routine on a typical working day.",
        "What kind of music do you like listening to, and why?",
        "Have you ever learned a new skill? Tell me about it.",
        "What do you usually do to relax after a busy day?",
        "Describe a memorable meal you had recently.",
        "What are your plans for the next holiday?",
    ],
    "2": [
        "Describe your favourite place to visit and explain why you like it.",
        "Talk about a book or film that made a strong impression on you.",
        "Describe a person who has influenced your life and explain how.",
        "Talk about a skill you would like to learn in the future and why.",
        "Describe a memorable trip you took and explain why it was special.",
        "Talk about the advantages and disadvantages of living in a big city.",
    ],
}

# ---------------------------------------------------------------------------
# PART 3: "For / Against" munozara jadvali formati.
# Har bir mavzu: bitta bahsli fikr (statement) + 3 ta "For" (rozi) va
# 3 ta "Against" (qarshi) dalil. Nomzod ikkala tomonni ham muhokama qilib,
# so'ng o'z fikrini bildirishi kerak.
# ---------------------------------------------------------------------------
PART_3_TOPICS = [
    {
        "statement": "Advertisement fast food should be banned.",
        "for": [
            "Clear link between the regular consumption and obesity",
            "No need to advertise fast food because it is already everywhere",
            "Advertising should encourage people to keep fit, not ruin their health",
        ],
        "against": [
            "For many people fast food is a more affordable choice than healthy food.",
            "Nowadays many fast food products have 'diet' version and 'classic' version.",
            "Freedom of choice is key element of a democratic society",
        ],
    },
    {
        "statement": "It is the waste of money to protect wild animals.",
        "for": [
            "Species will become extinct. It is a part of life.",
            "It is too costly so conservation programs can't raise enough funds to be successful.",
            "Money should be spent on education and healthcare.",
        ],
        "against": [
            "Loss of species disturbs the balance of the ecosystem.",
            "New medicines can be found by studying wild animals.",
            "Biodiversity is essential for the well-being of the planet.",
        ],
    },
    {
        "statement": "Universities should be free for everyone.",
        "for": [
            "Education is a basic right, not a privilege for the wealthy.",
            "Free education helps talented students from poor families succeed.",
            "A better-educated population benefits the whole economy.",
        ],
        "against": [
            "Free universities are extremely expensive for the government to fund.",
            "Students who pay for their education tend to take it more seriously.",
            "Limited resources mean quality of teaching could decrease.",
        ],
    },
    {
        "statement": "Social media does more harm than good to teenagers.",
        "for": [
            "It can lead to anxiety, depression, and low self-esteem.",
            "It exposes young people to cyberbullying and inappropriate content.",
            "It reduces the time spent on real face-to-face relationships.",
        ],
        "against": [
            "It helps teenagers stay connected with friends and family.",
            "It gives access to educational content and new skills.",
            "It allows young people to express creativity and find communities.",
        ],
    },
    {
        "statement": "Working from home should become the new normal for all office jobs.",
        "for": [
            "Employees save time and money by not commuting.",
            "People often feel more productive in a comfortable environment.",
            "It gives workers a better balance between work and family life.",
        ],
        "against": [
            "Face-to-face teamwork and creativity can suffer.",
            "Not everyone has a suitable space to work from home.",
            "It can be harder to separate work life from personal life.",
        ],
    },
    {
        "statement": "Zoos should be closed down completely.",
        "for": [
            "Animals suffer from stress living in small, artificial enclosures.",
            "Wild animals belong in their natural habitat, not in cages.",
            "Modern technology (documentaries, VR) can teach us about animals instead.",
        ],
        "against": [
            "Zoos play an important role in breeding endangered species.",
            "They raise public awareness and funding for conservation.",
            "Many zoo animals could not survive if released into the wild.",
        ],
    },
    {
        "statement": "Homework should be abolished in schools.",
        "for": [
            "It causes unnecessary stress for both students and parents.",
            "Children need more free time to rest, play, and develop other skills.",
            "There is little evidence that homework improves learning at a young age.",
        ],
        "against": [
            "Homework helps students practise and remember what they learned in class.",
            "It teaches responsibility, discipline, and time-management skills.",
            "It allows parents to stay involved in their children's education.",
        ],
    },
    {
        "statement": "Self-driving cars will make our roads safer.",
        "for": [
            "Most accidents are caused by human error, which computers can avoid.",
            "Self-driving cars can react faster than human drivers.",
            "They can reduce traffic jams by driving more efficiently.",
        ],
        "against": [
            "The technology is still new and can fail unexpectedly.",
            "Hacking or software errors could put passengers at serious risk.",
            "It will take years before laws and infrastructure are ready.",
        ],
    },
    {
        "statement": "Countries should invest more in space exploration than in solving problems on Earth.",
        "for": [
            "Space research often leads to new technologies used in everyday life.",
            "Finding new resources or planets could benefit humanity long-term.",
            "It inspires young people to study science and engineering.",
        ],
        "against": [
            "Millions of people still lack access to clean water and healthcare.",
            "The money could be used more effectively to fight poverty and climate change.",
            "Space exploration benefits are often too distant and uncertain.",
        ],
    },
    {
        "statement": "Plastic packaging should be completely banned.",
        "for": [
            "Plastic waste is seriously damaging oceans and wildlife.",
            "Alternatives like paper and glass are more environmentally friendly.",
            "A ban would force companies to innovate more sustainable packaging.",
        ],
        "against": [
            "Plastic is cheap and keeps many products fresh for longer.",
            "Alternative materials can be more expensive and less practical.",
            "Sudden bans could harm businesses that rely on plastic packaging.",
        ],
    },
    {
        "statement": "Children should not be allowed to use smartphones until they are teenagers.",
        "for": [
            "Early smartphone use is linked to shorter attention spans.",
            "It can expose young children to inappropriate content online.",
            "Children need to develop real social skills without constant screens.",
        ],
        "against": [
            "Smartphones can be useful learning tools with the right apps.",
            "They help parents stay in contact with their children for safety.",
            "Banning them completely may make children feel excluded from peers.",
        ],
    },
    {
        "statement": "Governments should ban the use of private cars in city centres.",
        "for": [
            "It would significantly reduce air pollution and traffic congestion.",
            "Public transport and cycling would become more attractive and used.",
            "City centres would become safer and quieter for pedestrians.",
        ],
        "against": [
            "It would be very inconvenient for people with disabilities or heavy shopping.",
            "Public transport in many cities is not yet reliable enough.",
            "Local businesses might lose customers who prefer to drive.",
        ],
    },
    {
        "statement": "Artificial intelligence will eventually replace most human jobs.",
        "for": [
            "AI can already perform many repetitive tasks faster and cheaper.",
            "Companies will naturally choose automation to reduce costs.",
            "History shows technology always replaces certain types of jobs.",
        ],
        "against": [
            "AI still lacks creativity, empathy, and complex human judgement.",
            "New technologies also tend to create new kinds of jobs.",
            "Many roles require a human touch that machines cannot replace.",
        ],
    },
    {
        "statement": "Tourism does more harm than good to popular destinations.",
        "for": [
            "Overcrowding damages historical sites and natural environments.",
            "Local prices often rise, making life harder for residents.",
            "Mass tourism can destroy the authentic culture of a place.",
        ],
        "against": [
            "Tourism creates jobs and boosts the local economy significantly.",
            "It can fund the preservation of historical and natural sites.",
            "It promotes cultural exchange and understanding between nations.",
        ],
    },
    {
        "statement": "All students should learn how to code at school.",
        "for": [
            "Coding is becoming an essential skill in almost every industry.",
            "It teaches logical thinking and problem-solving skills.",
            "Early exposure could inspire more students to pursue tech careers.",
        ],
        "against": [
            "Not every student is interested in or suited to programming.",
            "Schools already struggle to fit essential subjects into the timetable.",
            "Coding tools are changing so fast that lessons may become outdated quickly.",
        ],
    },
]


def _format_part3_topic(topic: dict) -> str:
    """'For / Against' mavzusini bitta matn ko'rinishiga formatlaydi."""
    for_lines = "\n".join(f"- {point}" for point in topic["for"])
    against_lines = "\n".join(f"- {point}" for point in topic["against"])
    return (
        f"{topic['statement']}\n\n"
        f"For:\n{for_lines}\n\n"
        f"Against:\n{against_lines}"
    )


def get_random_question(part: str) -> str:
    """Berilgan qism (part) uchun banki dan tasodifiy savol qaytaradi."""
    if part == "3":
        topic = random.choice(PART_3_TOPICS)
        return _format_part3_topic(topic)
    return random.choice(QUESTION_BANK[part])
