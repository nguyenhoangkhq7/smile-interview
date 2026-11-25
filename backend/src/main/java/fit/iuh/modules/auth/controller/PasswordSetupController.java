package fit.iuh.modules.auth.controller;

import fit.iuh.modules.auth.dto.PasswordSetupDtos.Redeem;
import fit.iuh.modules.auth.service.PasswordSetupService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/auth/password-setup")
@RequiredArgsConstructor
public class PasswordSetupController {
    private final PasswordSetupService service;

    @PostMapping
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void redeem(@Valid @RequestBody Redeem request) {
        service.redeem(request);
    }
}
