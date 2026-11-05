package fit.iuh.modules.questionbank.util;

import java.util.*;

/**
 * Comprehensive Domain Taxonomy Dictionary for IT Job Positions and Candidate Profiles.
 *
 * <p>Provides extensive bilingual (Vietnamese & English) keyword mapping across major industry domains:
 * Fintech, E-Commerce, Healthcare, EdTech, Logistics, SaaS, AI & Big Data, Telecom/IoT,
 * Media & Gaming, Travel/F&B, Real Estate, Cybersecurity, Enterprise, and Startup.
 *
 * <p>Uses weighted score aggregation to accurately determine the primary target domain of a job description or CV.
 */
public final class DomainTaxonomyDictionary {

    private DomainTaxonomyDictionary() {
        throw new UnsupportedOperationException("DomainTaxonomyDictionary is a utility class");
    }

    public static final String FINTECH = "fintech";
    public static final String E_COMMERCE = "e-commerce";
    public static final String HEALTHCARE = "healthcare";
    public static final String EDTECH = "edtech";
    public static final String LOGISTICS = "logistics";
    public static final String SAAS = "saas";
    public static final String AI_DATA = "ai_data";
    public static final String TELECOM = "telecom";
    public static final String MEDIA_GAMING = "media_gaming";
    public static final String TRAVEL_HOSPITALITY = "travel_hospitality";
    public static final String REAL_ESTATE = "real_estate";
    public static final String CYBERSECURITY = "cybersecurity";
    public static final String ENTERPRISE = "enterprise";
    public static final String STARTUP = "startup";
    public static final String OTHER = "other";

    private static final Map<String, List<String>> DOMAIN_KEYWORDS = new LinkedHashMap<>();

    static {
        // =========================================================================
        // 1. Fintech, Banking, Payment, Crypto & Insurtech
        // =========================================================================
        registerDomain(FINTECH, List.of(
                "fintech", "banking", "bank", "payment", "payments", "transaction", "transactions",
                "wallet", "e-wallet", "digital wallet", "credit", "credit card", "debit card",
                "loan", "lending", "mortgage", "investment", "stock", "stocks", "trading",
                "crypto", "cryptocurrency", "blockchain", "defi", "web3", "smart contract", "smart contracts",
                "insurance", "insurtech", "ledger", "general ledger", "pos", "payment gateway",
                "settlement", "remittance", "clearing", "core banking", "core-banking", "pci-dss", "pcidss",
                "aml", "kyc", "wealthtech", "open banking", "iso 20022", "swift transfer", "microfinance",
                "ngân hàng", "ngân hàng số", "tài chính", "thanh toán", "cổng thanh toán", "chứng khoán",
                "bảo hiểm", "tín dụng", "ví điện tử", "cho vay", "tiền tệ", "sổ cái", "giao dịch tài chính",
                "đầu tư", "tiền mã hóa", "tiền điện tử", "định danh tài khoản", "xác thực tài khoản",
                "chuyển tiền", "rút tiền", "thẻ tín dụng", "tài khoản ngân hàng", "bảo hiểm phi nhân thọ",
                "bảo hiểm nhân thọ", "thanh toán trực tuyến"
        ));

        // =========================================================================
        // 2. E-Commerce, Retail, Marketplace & D2C
        // =========================================================================
        registerDomain(E_COMMERCE, List.of(
                "e-commerce", "ecommerce", "retail", "shop", "shopping", "cart", "shopping cart",
                "checkout", "order", "orders", "order management", "store", "merchant", "merchants",
                "catalog", "marketplace", "omnichannel", "omni-channel", "inventory", "inventory management",
                "dropshipping", "flash sale", "promotion", "promotions", "discount", "voucher", "coupon",
                "b2c", "d2c", "pos system", "product catalog", "checkout flow", "shopping platform",
                "thương mại điện tử", "bán lẻ", "mua sắm", "giỏ hàng", "đơn hàng", "sàn thương mại",
                "sàn giao dịch", "cửa hàng", "gian hàng", "tồn kho", "quản lý kho hàng", "khuyến mãi",
                "mã giảm giá", "người bán", "người mua", "siêu thị", "chuỗi cửa hàng", "mua sắm trực tuyến",
                "sàn tmđt", "bán hàng đa kênh"
        ));

        // =========================================================================
        // 3. Healthcare, MedTech, BioTech & Pharma
        // =========================================================================
        registerDomain(HEALTHCARE, List.of(
                "health", "healthcare", "hospital", "hospitals", "medical", "medtech", "med-tech",
                "patient", "patients", "doctor", "doctors", "nurse", "clinic", "clinics",
                "ehr", "emr", "telemedicine", "telehealth", "pharmacy", "pharma", "biotech",
                "radiology", "laboratory", "prescription", "hipaa", "hl7", "fhir", "medical device",
                "clinical trial", "health record", "health informatics", "medical imaging",
                "y tế", "bệnh viện", "sức khỏe", "khám bệnh", "chữa bệnh", "phòng khám",
                "dược phẩm", "nhà thuốc", "thuốc", "bệnh nhân", "bác sĩ", "y tá", "bệnh án",
                "hồ sơ bệnh án", "bệnh án điện tử", "xét nghiệm", "chẩn đoán", "chẩn đoán hình ảnh",
                "bảo hiểm y tế", "y tế từ xa", "chăm sóc sức khỏe", "thiết bị y tế", "dược", "y dược"
        ));

        // =========================================================================
        // 4. EdTech, E-Learning, Education & Training
        // =========================================================================
        registerDomain(EDTECH, List.of(
                "education", "edtech", "ed-tech", "learning", "e-learning", "elearning", "school",
                "university", "course", "courses", "student", "students", "teacher", "teachers",
                "tutor", "curriculum", "lms", "learning management system", "classroom", "academy",
                "quiz", "quizzes", "exam", "examination", "assessment", "grading", "training",
                "pedagogy", "distance learning", "online learning", "courseware",
                "giáo dục", "học tập", "trường học", "đại học", "cao đẳng", "khóa học",
                "luyện thi", "đào tạo", "sinh viên", "học sinh", "giáo viên", "giảng viên",
                "gia sư", "bài giảng", "thi cử", "học trực tuyến", "chấm điểm", "học viện",
                "trường đại học", "quản lý học tập", "nền tảng học tập", "học liệu", "ôn thi"
        ));

        // =========================================================================
        // 5. Logistics, Supply Chain, Delivery & Transportation
        // =========================================================================
        registerDomain(LOGISTICS, List.of(
                "logistics", "supply chain", "warehouse", "warehousing", "shipping", "freight",
                "cargo", "fleet", "fleet management", "tracking", "delivery", "courier",
                "transportation", "wms", "tms", "last mile", "last-mile", "fulfillment", "customs",
                "container", "route optimization", "dispatch", "shipment", "freight forwarder",
                "vận tải", "vận chuyển", "kho bãi", "giao hàng", "giao nhận", "chuỗi cung ứng",
                "chuyển phát", "chuyển phát nhanh", "hàng hải", "đội xe", "định vị", "theo dõi đơn hàng",
                "thông quan", "hoàn tất đơn hàng", "tài xế", "giao vận", "kho vận", "tối ưu lộ trình",
                "bốc dỡ", "hàng hóa", "kho hàng", "vận chuyển đường bộ"
        ));

        // =========================================================================
        // 6. AI, Big Data, Machine Learning & Analytics
        // =========================================================================
        registerDomain(AI_DATA, List.of(
                "artificial intelligence", "machine learning", "deep learning", "nlp", "natural language processing",
                "computer vision", "llm", "large language model", "generative ai", "genai", "prompt engineering",
                "data warehouse", "data lake", "data pipeline", "etl", "elt", "spark", "hadoop", "kafka",
                "big data", "business intelligence", "data analytics", "data mining", "predictive modeling",
                "trí tuệ nhân tạo", "học máy", "học sâu", "dữ liệu lớn", "kho dữ liệu", "hồ dữ liệu",
                "xử lý ngôn ngữ tự nhiên", "thị giác máy tính", "mô hình ngôn ngữ lớn", "phân tích dữ liệu",
                "kỹ sư dữ liệu", "khoa học dữ liệu", "trích xuất dữ liệu", "dự đoán", "nhận diện hình ảnh"
        ));

        // =========================================================================
        // 7. SaaS, Cloud & Multi-tenant Business Software
        // =========================================================================
        registerDomain(SAAS, List.of(
                "saas", "software as a service", "multi-tenant", "multitenant", "cloud service",
                "subscription", "subscription model", "billing system", "b2b saas", "crm", "customer relationship management",
                "erp", "enterprise resource planning", "hrm", "human resource management", "ats", "applicant tracking",
                "helpdesk", "ticketing system", "workspace", "productivity tool", "collaboration tool",
                "phần mềm dịch vụ", "dịch vụ đám mây", "thuê bao", "quản trị nhân sự", "chăm sóc khách hàng",
                "quản lý quan hệ khách hàng", "hệ thống kế toán", "tính lương", "chấm công"
        ));

        // =========================================================================
        // 8. Media, Streaming, Entertainment & Gaming
        // =========================================================================
        registerDomain(MEDIA_GAMING, List.of(
                "media", "streaming", "video streaming", "audio streaming", "live streaming", "ott",
                "broadcasting", "content management", "cms", "game", "gaming", "gameplay", "game engine",
                "unity", "unreal engine", "esports", "music streaming", "vod", "video on demand",
                "truyền thông", "phát trực tuyến", "truyền hình", "nội dung số", "trò chơi",
                "trò chơi điện tử", "thể thao điện tử", "nhạc trực tuyến", "phim trực tuyến",
                "game online", "phát triển game", "lập trình game"
        ));

        // =========================================================================
        // 9. Travel, Hospitality, Booking & Food/Beverage
        // =========================================================================
        registerDomain(TRAVEL_HOSPITALITY, List.of(
                "travel", "tourism", "hospitality", "hotel", "hotels", "resort", "resorts",
                "booking", "reservation", "flight", "flights", "airline", "airlines", "restaurant",
                "restaurants", "food delivery", "food and beverage", "f&b", "ota", "online travel agency",
                "du lịch", "khách sạn", "nghỉ dưỡng", "đặt phòng", "đặt vé", "vé máy bay", "hàng không",
                "nhà hàng", "quán ăn", "giao đồ ăn", "ẩm thực", "đặt bàn", "tour du lịch"
        ));

        // =========================================================================
        // 10. Real Estate & PropTech
        // =========================================================================
        registerDomain(REAL_ESTATE, List.of(
                "real estate", "proptech", "prop-tech", "property", "properties", "housing",
                "apartment", "apartments", "condo", "landlord", "tenant", "listing", "real estate listing",
                "property management", "brokerage",
                "bất động sản", "nhà đất", "căn hộ", "chung cư", "thuê nhà", "mua bán nhà",
                "quản lý tòa nhà", "sàn bất động sản", "môi giới bất động sản", "địa ốc"
        ));

        // =========================================================================
        // 11. Cybersecurity, Infosec & Network Defense
        // =========================================================================
        registerDomain(CYBERSECURITY, List.of(
                "security", "cybersecurity", "cyber security", "infosec", "information security",
                "soc", "siem", "penetration testing", "pentest", "vulnerability", "firewall",
                "antivirus", "threat intelligence", "zero trust", "identity and access management", "iam",
                "an ninh mạng", "bảo mật", "an toàn thông tin", "mã độc", "tường lửa",
                "kiểm thử xâm nhập", "bảo mật hệ thống", "chống tấn công", "lỗ hổng bảo mật"
        ));

        // =========================================================================
        // 12. Telecommunications, IoT & Embedded Systems
        // =========================================================================
        registerDomain(TELECOM, List.of(
                "telecom", "telecommunication", "telecommunications", "iot", "internet of things",
                "5g", "4g", "lte", "voip", "sip", "embedded", "embedded systems", "firmware",
                "sensor", "sensors", "microcontroller", "smart home", "connected devices",
                "viễn thông", "mạng viễn thông", "nhúng", "hệ thống nhúng", "cảm biến",
                "thiết bị thông minh", "nhà thông minh", "thiết bị kết nối"
        ));

        // =========================================================================
        // 13. Enterprise B2B & Corporate Systems
        // =========================================================================
        registerDomain(ENTERPRISE, List.of(
                "enterprise", "b2b", "corporate", "enterprise grade", "enterprise architecture",
                "doanh nghiệp", "tập đoàn", "giải pháp doanh nghiệp"
        ));

        // =========================================================================
        // 14. Startup & Innovation
        // =========================================================================
        registerDomain(STARTUP, List.of(
                "startup", "start-up", "funding", "seed round", "series a", "series b",
                "mvp", "venture capital", "accelerator", "incubator", "early stage",
                "khởi nghiệp", "vốn đầu tư", "vòng gọi vốn"
        ));
    }

    private static void registerDomain(String domain, List<String> keywords) {
        DOMAIN_KEYWORDS.put(domain, keywords);
    }

    /**
     * Detects the primary target domain by scanning both CV and JD texts against domain lexicons.
     *
     * @param cvMarkdown Candidate CV text
     * @param jdMarkdown Job Description text
     * @return Detected target domain name (e.g. fintech, e-commerce, healthcare, ...) or "other"
     */
    public static String detectDomain(String cvMarkdown, String jdMarkdown) {
        String combined = ((cvMarkdown != null ? cvMarkdown : "") + " "
                + (jdMarkdown != null ? jdMarkdown : "")).toLowerCase(Locale.ROOT);

        if (combined.isBlank()) {
            return OTHER;
        }

        String bestDomain = OTHER;
        int maxScore = 0;

        for (Map.Entry<String, List<String>> entry : DOMAIN_KEYWORDS.entrySet()) {
            String domain = entry.getKey();
            List<String> keywords = entry.getValue();

            int score = 0;
            for (String kw : keywords) {
                if (kw.length() <= 3) {
                    // For short keywords (like pos, lms, aml, kyc, b2b, b2c, ehr, emr, iot, 5g, 4g, ott), check with word boundary logic
                    if (containsWord(combined, kw)) {
                        score += 2;
                    }
                } else if (combined.contains(kw)) {
                    // Longer phrase matches get higher weight proportional to specificity
                    score += kw.contains(" ") ? 3 : 1;
                }
            }

            if (score > maxScore) {
                maxScore = score;
                bestDomain = domain;
            }
        }

        // Require at least a minimal score threshold of 2 to avoid spurious matches
        return maxScore >= 2 ? bestDomain : (maxScore == 1 ? bestDomain : OTHER);
    }

    private static boolean containsWord(String text, String word) {
        int idx = text.indexOf(word);
        while (idx >= 0) {
            boolean startBoundary = (idx == 0) || !Character.isLetterOrDigit(text.charAt(idx - 1));
            int endIdx = idx + word.length();
            boolean endBoundary = (endIdx == text.length()) || !Character.isLetterOrDigit(text.charAt(endIdx));
            if (startBoundary && endBoundary) {
                return true;
            }
            idx = text.indexOf(word, idx + 1);
        }
        return false;
    }
}
