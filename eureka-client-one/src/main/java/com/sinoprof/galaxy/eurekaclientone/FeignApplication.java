package com.sinoprof.galaxy.eurekaclientone;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.web.servlet.support.SpringBootServletInitializer;
import org.springframework.cloud.client.circuitbreaker.EnableCircuitBreaker;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.cloud.netflix.hystrix.EnableHystrix;
import org.springframework.cloud.netflix.hystrix.dashboard.EnableHystrixDashboard;
import org.springframework.cloud.openfeign.EnableFeignClients;
import org.springframework.context.annotation.ComponentScan;

@SpringBootApplication
@EnableDiscoveryClient
@EnableFeignClients(basePackages = "com.sinoprof.galaxy.service")
@ComponentScan(basePackages = "com.sinoprof.galaxy")
@EnableHystrix
@EnableHystrixDashboard
@EnableCircuitBreaker
public class FeignApplication extends SpringBootServletInitializer {

    public static void main(String[] args) {
        SpringApplication.run(FeignApplication.class);
    }
}
