package fit.iuh.service;

import dev.langchain4j.data.document.Document;
import dev.langchain4j.data.document.splitter.DocumentByParagraphSplitter;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.model.openai.OpenAiTokenizer;
import fit.iuh.config.AppProperties;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.stream.Collectors;

/**
 * Service responsible for splitting standardized Markdown text into overlapping
 * token-aware chunks using LangChain4j's {@link DocumentByParagraphSplitter}.
 *
 * <p><strong>Strategy:</strong>
 * <ul>
 *   <li>Splits on paragraph boundaries first (preserving semantic coherence).</li>
 *   <li>Uses {@link OpenAiTokenizer} to measure token counts precisely.</li>
 *   <li>Merges adjacent paragraphs up to {@code maxTokens=512} per chunk.</li>
 *   <li>Adds {@code overlap=150} tokens between chunks to preserve context
 *       at chunk boundaries during retrieval.</li>
 * </ul>
 *
 * <p>Configuration is loaded from {@link AppProperties} → {@code app.chunking.*}.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ChunkingService {

    private final AppProperties appProperties;

    /**
     * Splits a Markdown text string into a list of overlapping text chunks.
     *
     * <p>The splitter respects paragraph boundaries to avoid cutting sentences
     * mid-way. Each returned chunk is trimmed and guaranteed to be non-blank.
     *
     * @param markdownText the Markdown text to split (output of StandardizationService)
     * @return ordered list of non-blank text chunk strings
     * @throws IllegalArgumentException if {@code markdownText} is null or blank
     */
    public List<String> chunkText(String markdownText) {
        if (markdownText == null || markdownText.isBlank()) {
            throw new IllegalArgumentException("Cannot chunk null or blank text.");
        }

        int maxTokens    = appProperties.getChunking().getMaxTokens();
        int overlapTokens = appProperties.getChunking().getOverlapTokens();

        log.debug("Chunking text ({} chars) with maxTokens={}, overlap={}",
                markdownText.length(), maxTokens, overlapTokens);

        // Use cl100k_base tokenizer (same as text-embedding-3-small) for accurate
        // token counting. The no-arg constructor is deprecated in LangChain4j 0.36.x.
        OpenAiTokenizer tokenizer = new OpenAiTokenizer("gpt-3.5-turbo");

        DocumentByParagraphSplitter splitter = new DocumentByParagraphSplitter(
                maxTokens,
                overlapTokens,
                tokenizer
        );

        Document document = Document.from(markdownText);
        List<TextSegment> segments = splitter.split(document);

        List<String> chunks = segments.stream()
                .map(TextSegment::text)
                .map(String::strip)
                .filter(text -> !text.isBlank())
                .collect(Collectors.toList());

        log.info("Chunking complete: {} segments produced from {} chars",
                chunks.size(), markdownText.length());

        return chunks;
    }
}
