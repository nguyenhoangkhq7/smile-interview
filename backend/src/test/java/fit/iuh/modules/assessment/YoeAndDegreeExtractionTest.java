package fit.iuh.modules.assessment;

import fit.iuh.modules.assessment.service.AssessmentCriteriaPreparer;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class YoeAndDegreeExtractionTest {

    private AssessmentCriteriaPreparer preparer;

    @BeforeEach
    void setUp() {
        preparer = new AssessmentCriteriaPreparer(null, null, null, null, null, null);
    }

    @Test
    @DisplayName("Extract numeric month date ranges: 01/2021 - 05/2023")
    void testNumericMonthDateRanges() {
        String text = "Worked as Backend Developer from 01/2021 - 05/2023.";
        double yoe = preparer.calculateCandidateYoe(text);
        assertTrue(yoe >= 2.0 && yoe <= 2.6, "YOE should be around 2.4 years, actual: " + yoe);
    }

    @Test
    @DisplayName("Extract word month date ranges: Jan 2021 - Mar 2023")
    void testWordMonthDateRanges() {
        String text = "Software Engineer at Tech Corp (Jan 2021 - Mar 2023)";
        double yoe = preparer.calculateCandidateYoe(text);
        assertTrue(yoe >= 2.0 && yoe <= 2.4, "YOE should be around 2.2 years, actual: " + yoe);
    }

    @Test
    @DisplayName("Extract Vietnamese format: Tháng 1/2021 - Tháng 12/2023")
    void testVietnameseMonthDateRanges() {
        String text = "Lập trình viên Java: Tháng 1/2021 - Tháng 12/2023";
        double yoe = preparer.calculateCandidateYoe(text);
        assertTrue(yoe >= 2.8 && yoe <= 3.1, "YOE should be around 3.0 years, actual: " + yoe);
    }

    @Test
    @DisplayName("Extract Year-only format: 2020 - 2023")
    void testYearOnlyDateRanges() {
        String text = "Fullstack Developer at ABC Company | 2020 - 2023";
        double yoe = preparer.calculateCandidateYoe(text);
        assertTrue(yoe >= 3.5 && yoe <= 4.1, "YOE for 2020-2023 should be around 4.0 years, actual: " + yoe);
    }

    @Test
    @DisplayName("Extract Experience Section without mixing Education dates")
    void testExperienceSectionIsolation() {
        String cvMarkdown = """
                # Tran Van B
                
                ## Education
                * 09/2017 - 06/2021: Ho Chi Minh City University of Technology (Bachelor of Computer Science)
                
                ## Work Experience
                * 07/2021 - 07/2023: Junior Java Developer at Company X
                * 08/2023 - Present: Mid Backend Developer at Company Y
                """;

        double yoe = preparer.calculateCandidateYoe(cvMarkdown);
        // Work experience is from 07/2021 to Present (about 3+ years), not counting 2017-2021 education
        assertTrue(yoe >= 3.0 && yoe <= 6.0, "YOE should only count work experience (approx 3-5 years), actual: " + yoe);
    }

    @Test
    @DisplayName("Check Degree in CV with various international & Vietnamese formats")
    void testCheckDegreeInCv() {
        assertTrue(preparer.checkDegreeInCv("B.S. in Computer Science from University of Science"));
        assertTrue(preparer.checkDegreeInCv("B.Sc in Software Engineering"));
        assertTrue(preparer.checkDegreeInCv("Tốt nghiệp Kỹ sư phần mềm Đại học Bách Khoa"));
        assertTrue(preparer.checkDegreeInCv("Bachelor of Information Technology - FPT University"));
        assertTrue(preparer.checkDegreeInCv("Master of Science in Artificial Intelligence"));
        assertTrue(preparer.checkDegreeInCv("Cử nhân Công nghệ Thông tin"));
        
        // Negative test: High school only
        assertFalse(preparer.checkDegreeInCv("High school graduate with 2 years of self-taught coding"));
        assertFalse(preparer.checkDegreeInCv(""));
        assertFalse(preparer.checkDegreeInCv(null));
    }

    @Test
    @DisplayName("Extract Year-first date ranges: 2021.05 - 2023.08 and 2022-01 - Present")
    void testYearFirstDateRanges() {
        String text1 = "Backend Developer (2021.05 - 2023.08)";
        double yoe1 = preparer.calculateCandidateYoe(text1);
        assertTrue(yoe1 >= 2.1 && yoe1 <= 2.4, "YOE should be around 2.3 years, actual: " + yoe1);

        String text2 = "Software Engineer (2021/01 - 2023/12)";
        double yoe2 = preparer.calculateCandidateYoe(text2);
        assertTrue(yoe2 >= 2.8 && yoe2 <= 3.1, "YOE should be around 3.0 years, actual: " + yoe2);
    }

    @Test
    @DisplayName("Parse required YoE avoiding framework versions and calendar years")
    void testParseRequiredYoeEdgeCases() {
        // Framework versions like Java 11 / 17 or .NET 6 should not be parsed as required YoE
        assertEquals(3.0, fit.iuh.modules.assessment.util.ResumeHeuristicsUtil.parseRequiredYoe("Kinh nghiệm Java 11, Java 17, tối thiểu 3 năm kinh nghiệm"));
        assertEquals(2.0, fit.iuh.modules.assessment.util.ResumeHeuristicsUtil.parseRequiredYoe("Requires 2+ years of experience with .NET 6 and C#"));
        assertEquals(5.0, fit.iuh.modules.assessment.util.ResumeHeuristicsUtil.parseRequiredYoe("At least 5 years experience, graduated in 2020"));
        assertEquals(0.0, fit.iuh.modules.assessment.util.ResumeHeuristicsUtil.parseRequiredYoe("Java 8 / Java 11 backend development"));
    }

    @Test
    @DisplayName("Check Degree in CV with negative phrases and degree level distinction")
    void testCheckDegreeInCvEdgeCases() {
        // Explicit negation
        assertFalse(fit.iuh.modules.assessment.util.ResumeHeuristicsUtil.checkDegreeInCv("Học sinh cấp 3, không có bằng đại học, tự học lập trình"));
        assertFalse(fit.iuh.modules.assessment.util.ResumeHeuristicsUtil.checkDegreeInCv("Self-taught developer, no university degree"));

        // Degree level checks
        assertTrue(fit.iuh.modules.assessment.util.ResumeHeuristicsUtil.checkDegreeInCv("Master of Science in CS", "Master Degree"));
        assertFalse(fit.iuh.modules.assessment.util.ResumeHeuristicsUtil.checkDegreeInCv("Bachelor of Information Technology", "Master Degree in Computer Science"));
        assertTrue(fit.iuh.modules.assessment.util.ResumeHeuristicsUtil.checkDegreeInCv("Tốt nghiệp Đại học Bách Khoa", "Yêu cầu bằng Đại học CNTT"));
        assertFalse(fit.iuh.modules.assessment.util.ResumeHeuristicsUtil.checkDegreeInCv("Tốt nghiệp Cao đẳng nghề CNTT", "Yêu cầu bằng Đại học chuyên ngành CNTT"));
    }

    @Test
    @DisplayName("Extract Experience Section with Bold Markdown: **Kinh nghiệm làm việc**")
    void testBoldMarkdownExperienceHeader() {
        String cvMarkdown = """
                **Học vấn**
                09/2018 - 06/2022: Đại học Bách Khoa
                
                **Kinh nghiệm làm việc**
                07/2022 - 07/2024: Backend Engineer tại FPT Software
                """;

        double yoe = preparer.calculateCandidateYoe(cvMarkdown);
        assertTrue(yoe >= 1.9 && yoe <= 2.3, "YOE should be approx 2.0 years, actual: " + yoe);
    }

    @Test
    @DisplayName("Academic Projects & Personal Projects should not be counted as professional work experience")
    void testAcademicAndPersonalProjectsExclusion() {
        String cvWithAcademicProjects = """
                # Student Profile
                ## Education
                * 09/2019 - 06/2023: Computer Science Bachelor
                
                ## Academic Projects
                * 01/2021 - 12/2022: Graduation thesis and coursework projects in Java
                
                ## Personal Projects
                * 01/2023 - 12/2023: E-commerce pet project using React
                """;

        double yoe = preparer.calculateCandidateYoe(cvWithAcademicProjects);
        assertEquals(0.0, yoe, "Academic and personal projects must not be counted as professional experience");
    }

    @Test
    @DisplayName("Extract Full numeric Day/Month/Year date range: 15/05/2021 - 20/08/2023")
    void testFullNumericDayMonthYearDateRange() {
        String text = "Senior Java Developer (15/05/2021 - 20/08/2023) at Tech Corp";
        double yoe = preparer.calculateCandidateYoe(text);
        assertTrue(yoe >= 2.1 && yoe <= 2.4, "YOE should be around 2.3 years for 15/05/2021 - 20/08/2023, actual: " + yoe);
    }

    @Test
    @DisplayName("Detect INTERN seniority level when 0 YOE and intern keywords exist")
    void testInternSeniorityLevelDetection() {
        var metadataExtractor = new fit.iuh.modules.assessment.service.JdMetadataExtractor(null, null, null);
        String internCv = """
                # Nguyen Van C
                Third-year IT student seeking Java Intern / Internship Trainee position.
                Skills: Java Core, Spring Boot, MySQL.
                """;

        var level = metadataExtractor.extractCvSeniorityLevel(internCv);
        assertEquals(fit.iuh.modules.assessment.entity.SeniorityLevel.INTERN, level, "Student with 0 YOE and intern keywords should be INTERN");
    }
}
