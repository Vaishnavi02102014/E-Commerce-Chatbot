from semantic_router import Route
from semantic_router.routers import SemanticRouter
from semantic_router.encoders import HuggingFaceEncoder

# ----- encoder -----
encoder = HuggingFaceEncoder(name="sentence-transformers/all-MiniLM-L6-v2")

# ----- routes -----
faq = Route(
    name="faq",
    utterances=[
        "What’s your return policy?",
        "What is your return policy?",
        "Tell me about your return policy",
        "How do returns work?",
        "How can I cancel my order?",
        "Do you offer international shipping?",
        "How can I contact customer support?",
        "What payment methods do you accept?",
        "Do you provide cash on delivery?",
        "What’s your policy on defective products?",
        "What is your defective product policy?",
        "Policy for damaged or faulty items",
        "If product is defective, what to do?",
        "Who do I contact for a damaged order?",
        "What is the return policy of the products?",
        "Do I get discount with the HDFC credit card?",
        "How can I track my order?",
        "What payment methods are accepted?",
        "How long does it take to process a refund?",
    ],
)

product = Route(
    name="product",
    utterances=[
        "Show me smartphones under 20000",
        "Smartphones below 20000",
        "Pink puma shoes under 10000",
        "Wireless earbuds in stock",
        "Price of iPhone 15 Pro",
        "Laptops for gaming",
        "Red dress size M",
        "Discounts on shoes",
        "Deliver this product tomorrow",
        "I want to buy nike shoes that have 50% discount.",
        "Are there any shoes under Rs. 3000?",
        "Do you have formal shoes in size 9?",
        "Are there any Puma shoes on sale?",
        "What is the price of puma running shoes?",
    ],
)

routes = [faq, product]

# ----- router -----
router = SemanticRouter(encoder=encoder, routes=routes, auto_sync="local")

