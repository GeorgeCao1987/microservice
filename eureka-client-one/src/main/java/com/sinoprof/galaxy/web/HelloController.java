package com.sinoprof.galaxy.web;

import com.sinoprof.galaxy.service.HelloService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HelloController {
    private static final Logger LOGGER = LoggerFactory.getLogger(HelloController.class);

    @Autowired
    private HelloService service;
    @Value("${server.port}")
    private String port;

    @RequestMapping(value = "/test")
    public String sayHello(String username) {
        LOGGER.info("service one, port=" + port + ", username=" + username);
        return service.sayHello(username);
    }
}
