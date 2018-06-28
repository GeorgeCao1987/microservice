package com.sinoprof.galaxy.hystrix;

import com.sinoprof.galaxy.service.HelloService;
import org.springframework.stereotype.Component;

@Component
public class HelloServiceFallbackHandler implements HelloService {

    @Override
    public String sayHello(String username) {
        return "error";
    }
}
