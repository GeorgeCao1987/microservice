package com.sinoprof.galaxy.service;

import com.sinoprof.galaxy.hystrix.HelloServiceFallbackHandler;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;

@FeignClient(value = "service-two", fallback = HelloServiceFallbackHandler.class)
public interface HelloService {

    @RequestMapping("/test")
    String sayHello(@RequestParam("username") String username);
}
