"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import images from "@/images/Interview.jpg";
import Jman_img from "@/images/JmanLogo.png";
import { AnimatedInView } from "@/components/animation/AnimatedInView";

const loginSchema = z.object({
  email: z
    .string()
    .nonempty({ message: "Email or username is required" })
    .regex(
      /^([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}|[a-zA-Z0-9]+)$/,
      "Invalid email or username"
    ),
  password: z.string().min(6, "Password must be at least 6 characters"),
});

export default function LoginPage() {
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();
  const router = useRouter();

  const form = useForm<z.infer<typeof loginSchema>>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  async function onSubmit(values: z.infer<typeof loginSchema>) {
    try {
      setIsLoading(true);

      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Login failed");
      }

      router.push(data.redirect);
      toast({ title: "Success", description: "Logged in successfully" });
    } catch (error) {
      toast({
        variant: "destructive",
        title: "Error",
        description: "Invalid credentials",
      });
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <AnimatedInView className="min-h-dvh bg-gray-50">
      {/* 2-column responsive layout */}
      <div className="mx-auto grid min-h-dvh w-full grid-cols-1 md:grid-cols-2">
        {/* Left: form */}
        <div className="relative flex items-center justify-center bg-card px-6 py-10">
          <div className="absolute top-4 left-4 flex items-center space-x-2">
            <Image
              src={Jman_img}
              alt="Company Logo"
              width={25}
              height={14}
              className="object-contain"
            />
            <span className="text-md font-bold text-primary">JMAN Group</span>
          </div>

          <div className="w-full max-w-sm rounded-lg bg-white p-6 space-y-6">
            <div className="flex flex-col items-center space-y-2">
              <h2 className="text-xl font-semibold">Welcome to JHire</h2>
              <p className="text-xs text-muted-foreground">
                Sign in to your account
              </p>
            </div>

            <Form {...form}>
              <form
                onSubmit={form.handleSubmit(onSubmit)}
                className="space-y-4"
                autoComplete="off"
              >
                <FormField
                  control={form.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Email address</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="Your Email"
                          autoComplete="off"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage className="text-xs" />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Password</FormLabel>
                      <FormControl>
                        <Input
                          type="password"
                          autoComplete="off"
                          {...field}
                          className="h-8 text-sm px-2"
                        />
                      </FormControl>
                      <FormMessage className="text-xs" />
                    </FormItem>
                  )}
                />
                <Button
                  type="submit"
                  className="w-full h-8 text-sm"
                  disabled={isLoading}
                >
                  {isLoading ? "Signing in..." : "Sign in"}
                </Button>
              </form>
            </Form>
          </div>
        </div>

        {/* Right: hero image */}
        <div className="relative hidden md:block">
          <Image
            src={images}
            alt="Login Illustration"
            fill
            className="object-cover"
            priority
          />
        </div>
      </div>
    </AnimatedInView>
  );
}
