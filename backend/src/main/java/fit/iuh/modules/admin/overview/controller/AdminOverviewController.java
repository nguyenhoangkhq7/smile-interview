package fit.iuh.modules.admin.overview.controller;

import fit.iuh.modules.admin.overview.dto.AdminOverviewResponse;
import fit.iuh.modules.admin.overview.service.AdminOverviewService;
import fit.iuh.modules.admin.overview.model.OverviewRange;
import lombok.RequiredArgsConstructor;
import org.springframework.http.CacheControl;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/admin/overview")
@RequiredArgsConstructor
public class AdminOverviewController {
    private final AdminOverviewService service;

    @GetMapping
    public ResponseEntity<AdminOverviewResponse> overview(@RequestParam(defaultValue = "30d") String range) {
        OverviewRange selected = OverviewRange.fromKey(range).orElseThrow(() ->
                new ResponseStatusException(HttpStatus.BAD_REQUEST, "range must be one of 7d, 30d, 90d, all"));
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(service.load(selected));
    }
}
