package com.example.service

import com.example.greeter.Greeter

fun serve(name: String): String = Greeter.greet(name)
