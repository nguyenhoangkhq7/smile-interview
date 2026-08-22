package fit.iuh.modules.questionbank;

import fit.iuh.modules.questionbank.util.DomainTaxonomyDictionary;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class DomainTaxonomyDictionaryTest {

    @Test
    @DisplayName("Detects Fintech & Banking from Vietnamese and English keywords")
    void testFintechDetection() {
        assertEquals("fintech", DomainTaxonomyDictionary.detectDomain("", "Tuyển lập trình viên Core Banking, xử lý giao dịch tài chính và ví điện tử"));
        assertEquals("fintech", DomainTaxonomyDictionary.detectDomain("Experience in payment gateway, smart contracts and crypto trading", ""));
        assertEquals("fintech", DomainTaxonomyDictionary.detectDomain("", "Phát triển hệ thống sổ cái tín dụng và cho vay trực tuyến"));
    }

    @Test
    @DisplayName("Detects E-Commerce & Retail from Vietnamese and English keywords")
    void testEcommerceDetection() {
        assertEquals("e-commerce", DomainTaxonomyDictionary.detectDomain("", "Xây dựng hệ thống sàn thương mại điện tử, giỏ hàng và flash sale"));
        assertEquals("e-commerce", DomainTaxonomyDictionary.detectDomain("Built product catalog and checkout flow for retail shop", ""));
        assertEquals("e-commerce", DomainTaxonomyDictionary.detectDomain("", "Quản lý mã giảm giá và đơn hàng cho chuỗi siêu thị"));
    }

    @Test
    @DisplayName("Detects Healthcare & MedTech from Vietnamese and English keywords")
    void testHealthcareDetection() {
        assertEquals("healthcare", DomainTaxonomyDictionary.detectDomain("", "Phát triển phần mềm quản lý bệnh viện, hồ sơ bệnh án điện tử và khám bệnh từ xa"));
        assertEquals("healthcare", DomainTaxonomyDictionary.detectDomain("Designed HIPAA-compliant EHR platform for doctors and patients", ""));
        assertEquals("healthcare", DomainTaxonomyDictionary.detectDomain("", "Hệ thống quản lý nhà thuốc và chẩn đoán hình ảnh y tế"));
    }

    @Test
    @DisplayName("Detects EdTech & E-Learning from Vietnamese and English keywords")
    void testEdTechDetection() {
        assertEquals("edtech", DomainTaxonomyDictionary.detectDomain("", "Nền tảng học tập trực tuyến, quản lý khóa học và thi cử cho sinh viên"));
        assertEquals("edtech", DomainTaxonomyDictionary.detectDomain("Implemented LMS platform with quiz grading and classroom tools", ""));
    }

    @Test
    @DisplayName("Detects Logistics & Supply Chain from Vietnamese and English keywords")
    void testLogisticsDetection() {
        assertEquals("logistics", DomainTaxonomyDictionary.detectDomain("", "Hệ thống quản lý kho bãi, định vị đơn hàng và chuyển phát nhanh cho tài xế"));
        assertEquals("logistics", DomainTaxonomyDictionary.detectDomain("Optimized fleet route and warehouse inventory dispatch", ""));
    }

    @Test
    @DisplayName("Detects AI & Big Data from Vietnamese and English keywords")
    void testAiDataDetection() {
        assertEquals("ai_data", DomainTaxonomyDictionary.detectDomain("", "Xây dựng mô hình trí tuệ nhân tạo, xử lý ngôn ngữ tự nhiên và kho dữ liệu"));
        assertEquals("ai_data", DomainTaxonomyDictionary.detectDomain("Engineered ETL pipelines using Spark and Kafka for predictive analytics", ""));
    }

    @Test
    @DisplayName("Detects SaaS, Cybersecurity, Media/Gaming and other domains")
    void testOtherDomains() {
        assertEquals("saas", DomainTaxonomyDictionary.detectDomain("", "Multi-tenant cloud service platform with subscription billing"));
        assertEquals("cybersecurity", DomainTaxonomyDictionary.detectDomain("", "Chuyên viên an ninh mạng, kiểm thử xâm nhập và phòng chống mã độc"));
        assertEquals("media_gaming", DomainTaxonomyDictionary.detectDomain("", "Lập trình game Unity và hệ thống phát trực tuyến video"));
        assertEquals("travel_hospitality", DomainTaxonomyDictionary.detectDomain("", "Nền tảng đặt phòng khách sạn và vé máy bay"));
        assertEquals("real_estate", DomainTaxonomyDictionary.detectDomain("", "Sàn giao dịch bất động sản và môi giới nhà đất"));
        assertEquals("telecom", DomainTaxonomyDictionary.detectDomain("", "Hệ thống mạng viễn thông 5G và thiết bị nhà thông minh IoT"));
        assertEquals("startup", DomainTaxonomyDictionary.detectDomain("", "Early-stage startup building MVP for seed round funding"));
    }

    @Test
    @DisplayName("Returns 'other' when no domain keywords match")
    void testFallbackOther() {
        assertEquals("other", DomainTaxonomyDictionary.detectDomain("", ""));
        assertEquals("other", DomainTaxonomyDictionary.detectDomain("Generic generic generic", "Nothing specific"));
    }
}
