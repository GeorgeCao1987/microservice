package com.george.galaxy.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HelloService {
    private static final Logger LOGGER = LoggerFactory.getLogger(HelloService.class);

    @Value("${server.port}")
    private String port;

    @RequestMapping("/test")
    public String test(String username) {
        LOGGER.info("service2, port=" + port);
        return "Hello, " + username + "!";
    }
}
